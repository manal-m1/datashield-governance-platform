"""
D.4 - Simulated drift detection delay.

Simulates a transition from a normal data distribution
to a risky distribution and measures the delay between:

    T_drift
        =
    moment when risky data starts

and

    T_detection
        =
    first detection triggered by StreamShield logic.

The experiment reproduces the detection trigger logic
used by StreamShieldConsumer:

    - every 50 messages
    - OR every 15 seconds
    - only if window_size >= 20
"""

import asyncio
import os
import sys
import time
import csv

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../.."
        )
    )
)

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


# ============================================================
# CONFIGURATION
# ============================================================

PARTITION = 0

N_MIN = 20
THRESHOLD = 0.7

DETECTION_INTERVAL = 50
DETECTION_TIMEOUT = 15

WINDOW_MIN_SIZE = 20

NORMAL_MESSAGES = 40
RISKY_MESSAGES = 100

MESSAGE_INTERVAL = 0.05

FIELDS = ("ville", "sexe")

N_RUNS = 5

OUTPUT_CSV = os.path.join(
    os.path.dirname(__file__),
    "results",
    "drift_detection_delay.csv"
)


# ============================================================
# DATA GENERATION
# ============================================================

def generate_normal_record(run_id, index):
    """
    Normal profile.

    Large equivalence class:
        k is high
        uniqueness is low
        expected risk is low
    """

    return {
        "event_id": f"normal-{run_id}-{index}",
        "ville": "NormalVille",
        "sexe": "M"
    }


def generate_risky_record(run_id, index):
    """
    Risky profile.

    Each equivalence class is repeated twice:

        k = 2

    This reproduces the risky pattern validated in D.2.
    """

    class_id = index // 2

    ville = f"RiskyVille_{run_id}_{class_id}"
    sexe = "M" if class_id % 2 == 0 else "F"

    return {
        "event_id": f"risky-{run_id}-{index}",
        "ville": ville,
        "sexe": sexe
    }


# ============================================================
# SINGLE RUN
# ============================================================

async def run_experiment(
    scorer,
    run_id
):

    print()
    print("-" * 70)
    print(f"RUN {run_id}")
    print("-" * 70)

    records = []

    messages_since_detection = 0

    last_detection_time = time.perf_counter()

    drift_time = None
    detection_time = None

    detection_reason = None

    # --------------------------------------------------------
    # Phase 1 - normal traffic
    # --------------------------------------------------------

    print(
        f"Normal phase: "
        f"{NORMAL_MESSAGES} messages"
    )

    for i in range(NORMAL_MESSAGES):

        record = generate_normal_record(
            run_id,
            i
        )

        records.append(record)

        messages_since_detection += 1

        await asyncio.sleep(
            MESSAGE_INTERVAL
        )

    # --------------------------------------------------------
    # Drift starts HERE
    # --------------------------------------------------------

    drift_time = time.perf_counter()

    print(
        f"DRIFT STARTED at t={drift_time:.6f}"
    )

    # --------------------------------------------------------
    # Phase 2 - risky traffic
    # --------------------------------------------------------

    for i in range(RISKY_MESSAGES):

        record = generate_risky_record(
            run_id,
            i
        )

        records.append(record)

        messages_since_detection += 1

        now = time.perf_counter()

        current_window_size = len(records)

        count_trigger = (
            messages_since_detection
            >= DETECTION_INTERVAL
        )

        time_trigger = (
            (now - last_detection_time)
            >= DETECTION_TIMEOUT
            and current_window_size
            >= WINDOW_MIN_SIZE
        )

        # ----------------------------------------------------
        # Detection trigger
        # ----------------------------------------------------

        if count_trigger or time_trigger:

            detection_reason = (
                "count"
                if count_trigger
                else "timeout"
            )

            detection_time = now

            # Evaluate current window
            result = scorer.score(
                records,
                FIELDS
            )

            print(
                f"Detection triggered | "
                f"reason={detection_reason} | "
                f"messages_since_detection="
                f"{messages_since_detection} | "
                f"window={current_window_size} | "
                f"k={result.k} | "
                f"risk={result.score:.4f} | "
                f"triggered={result.triggered}"
            )

            # We only care about the first
            # risk detection after drift.
            if result.triggered:

                break

            messages_since_detection = 0
            last_detection_time = now

        await asyncio.sleep(
            MESSAGE_INTERVAL
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    if detection_time is None:

        print(
            "NO DETECTION during experiment"
        )

        return {
            "run_id": run_id,
            "drift_detected": False,
            "detection_reason": "",
            "delay_seconds": None
        }

    delay = (
        detection_time - drift_time
    )

    print(
        f"Drift detection delay = "
        f"{delay:.6f} seconds"
    )

    return {
        "run_id": run_id,
        "drift_detected": True,
        "detection_reason": detection_reason,
        "delay_seconds": delay
    }


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("STREAMSHIELD - D.4 SIMULATED DRIFT DETECTION")
    print("=" * 70)

    print()
    print(f"Normal messages      : {NORMAL_MESSAGES}")
    print(f"Risky messages       : {RISKY_MESSAGES}")
    print(f"Detection interval   : {DETECTION_INTERVAL} messages")
    print(f"Detection timeout    : {DETECTION_TIMEOUT} seconds")
    print(f"Minimum window       : {WINDOW_MIN_SIZE}")
    print(f"Message interval     : {MESSAGE_INTERVAL}s")
    print(f"Runs                 : {N_RUNS}")

    scorer = FuzzyRiskScorer(
        threshold=THRESHOLD,
        min_sample_size=N_MIN
    )

    await scorer.load_fuzzy_configuration()

    results = []

    for run_id in range(
        1,
        N_RUNS + 1
    ):

        result = await run_experiment(
            scorer,
            run_id
        )

        results.append(result)

    # ========================================================
    # Statistics
    # ========================================================

    detected = [
        r
        for r in results
        if r["drift_detected"]
    ]

    if detected:

        delays = [
            r["delay_seconds"]
            for r in detected
        ]

        mean_delay = (
            sum(delays)
            / len(delays)
        )

        min_delay = min(delays)
        max_delay = max(delays)

    else:

        mean_delay = None
        min_delay = None
        max_delay = None

    # ========================================================
    # Save CSV
    # ========================================================

    os.makedirs(
        os.path.dirname(OUTPUT_CSV),
        exist_ok=True
    )

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "drift_detected",
                "detection_reason",
                "delay_seconds"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    # ========================================================
    # Summary
    # ========================================================

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"Detected runs : "
        f"{len(detected)}/{N_RUNS}"
    )

    if detected:

        print(
            f"Mean delay    : "
            f"{mean_delay:.4f} s"
        )

        print(
            f"Min delay     : "
            f"{min_delay:.4f} s"
        )

        print(
            f"Max delay     : "
            f"{max_delay:.4f} s"
        )

    else:

        print(
            "No drift detection."
        )

    print()
    print(
        f"CSV saved to: "
        f"{OUTPUT_CSV}"
    )

    print()
    print("=" * 70)
    print("D.4 FINISHED")
    print("=" * 70)


if __name__ == "__main__":

    asyncio.run(main())