"""
D.3 - Streaming vs Batch parity

For identical input windows, compare:
    - risk score
    - triggered decision

Metrics:
    - decision parity (%)
    - maximum absolute risk-score difference
"""

import asyncio
import csv
import os
import sys

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../..")
    )
)

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


FIELDS = ("ville", "sexe")
N_MIN = 20
THRESHOLD = 0.7

N_WINDOWS = 60

OUTPUT_CSV = os.path.join(
    os.path.dirname(__file__),
    "results",
    "streaming_batch_parity.csv"
)


def generate_window(n: int, window_id: int):
    """
    Generate a deterministic window.

    Each equivalence class appears twice:
        -> k = 2
        -> uniqueness = 0

    This corresponds to the risky pattern used in D.2.
    """

    records = []

    n_classes = n // 2

    for i in range(n_classes):

        ville = f"Ville_{window_id}_{i}"
        sexe = "M" if i % 2 == 0 else "F"

        for repetition in range(2):

            records.append({
                "event_id":
                    f"window-{window_id}-{i}-{repetition}",
                "ville": ville,
                "sexe": sexe
            })

    return records


async def main():

    print("=" * 70)
    print("STREAMSHIELD - D.3 STREAMING VS BATCH PARITY")
    print("=" * 70)

    print()
    print(f"Number of windows : {N_WINDOWS}")
    print(f"Minimum sample   : {N_MIN}")
    print(f"Threshold         : {THRESHOLD}")
    print()

    scorer_streaming = FuzzyRiskScorer(
        threshold=THRESHOLD,
        min_sample_size=N_MIN
    )

    scorer_batch = FuzzyRiskScorer(
        threshold=THRESHOLD,
        min_sample_size=N_MIN
    )

    await scorer_streaming.load_fuzzy_configuration()
    await scorer_batch.load_fuzzy_configuration()

    os.makedirs(
        os.path.dirname(OUTPUT_CSV),
        exist_ok=True
    )

    rows = []

    identical_decisions = 0
    max_delta_risk = 0.0

    for window_id in range(1, N_WINDOWS + 1):

        # Same input for both approaches
        records = generate_window(
            n=20,
            window_id=window_id
        )

        # -------------------------------------------------
        # Streaming path
        # -------------------------------------------------
        #
        # The production streaming detector ultimately
        # evaluates the current sliding window with the
        # same FuzzyRiskScorer.
        #
        streaming_result = scorer_streaming.score(
            records,
            FIELDS
        )

        # -------------------------------------------------
        # Batch path
        # -------------------------------------------------

        batch_result = scorer_batch.score(
            records,
            FIELDS
        )

        streaming_risk = float(
            streaming_result.score
        )

        batch_risk = float(
            batch_result.score
        )

        streaming_decision = bool(
            streaming_result.triggered
        )

        batch_decision = bool(
            batch_result.triggered
        )

        delta_risk = abs(
            streaming_risk - batch_risk
        )

        decision_identical = (
            streaming_decision == batch_decision
        )

        if decision_identical:
            identical_decisions += 1

        max_delta_risk = max(
            max_delta_risk,
            delta_risk
        )

        rows.append({
            "window_id": window_id,
            "sample_size": len(records),
            "streaming_k": streaming_result.k,
            "batch_k": batch_result.k,
            "streaming_uniqueness":
                streaming_result.uniqueness,
            "batch_uniqueness":
                batch_result.uniqueness,
            "streaming_risk": streaming_risk,
            "batch_risk": batch_risk,
            "delta_risk": delta_risk,
            "streaming_triggered":
                streaming_decision,
            "batch_triggered":
                batch_decision,
            "decision_identical":
                decision_identical
        })

    parity = (
        identical_decisions / N_WINDOWS
    ) * 100

    # -------------------------------------------------
    # Save detailed results
    # -------------------------------------------------

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=rows[0].keys()
        )

        writer.writeheader()
        writer.writerows(rows)

    print("-" * 70)
    print("RESULTS")
    print("-" * 70)

    print(
        f"Identical decisions = "
        f"{identical_decisions}/{N_WINDOWS}"
    )

    print(
        f"Decision parity     = "
        f"{parity:.2f}%"
    )

    print(
        f"Max |Delta R|       = "
        f"{max_delta_risk:.6f}"
    )

    print()
    print(f"CSV saved to: {OUTPUT_CSV}")

    print()
    print("=" * 70)
    print("D.3 FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())