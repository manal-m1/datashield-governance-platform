import asyncio
import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt

# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


# ============================================================
# CONFIGURATION
# ============================================================

N_MINS = [10, 20, 50, 100]

N_WINDOWS = 30

THRESHOLD = 0.7

FIELDS = ("ville", "sexe")

ROOT = Path(__file__).resolve().parent

RESULTS_DIR = ROOT / "results"
PLOTS_DIR = ROOT / "plots"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# NORMAL WINDOW
# ============================================================
def generate_normal_window(n: int, seed: int):
    """
    Normal window:
    every (ville, sexe) combination appears n times.

    Therefore:
        k = n
        uniqueness = 0

    For n >= 10, k is sufficiently high and the
    resulting fuzzy score remains below the alert threshold.
    """

    return [
        {
            "event_id": f"normal-{seed}-{i}",
            "ville": "NormalVille",
            "sexe": "M",
        }
        for i in range(n)
    ]


def generate_risky_window(n: int, seed: int):
    """
    Risky window:
    every (ville, sexe) combination appears exactly twice.

    Therefore:
        k = 2
        uniqueness = 0

    The number of distinct combinations grows with n,
    while the minimum equivalence-class size remains 2.
    """

    records = []

    for i in range(n // 2):

        ville = f"RiskyVille_{seed}_{i}"

        sexe = "M" if i % 2 == 0 else "F"

        for repetition in range(2):

            records.append({
                "event_id": (
                    f"risky-{seed}-{i}-{repetition}"
                ),
                "ville": ville,
                "sexe": sexe,
            })

    return records

# ============================================================
# METRICS
# ============================================================

def compute_metrics(predictions, labels):

    tp = tn = fp = fn = 0

    for prediction, label in zip(predictions, labels):

        if label == 1 and prediction == 1:
            tp += 1

        elif label == 0 and prediction == 0:
            tn += 1

        elif label == 0 and prediction == 1:
            fp += 1

        elif label == 1 and prediction == 0:
            fn += 1

    fpr = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0.0
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    accuracy = (
        (tp + tn) / len(labels)
        if labels
        else 0.0
    )

    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "FPR": fpr,
        "Recall": recall,
        "Precision": precision,
        "Accuracy": accuracy,
    }


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("STREAMSHIELD - D.2 FALSE ALERT ANALYSIS")
    print("=" * 70)

    print()
    print(f"Normal windows : {N_WINDOWS}")
    print(f"Risky windows  : {N_WINDOWS}")
    print(f"N_min values   : {N_MINS}")
    print()

    all_results = []

    # ========================================================
    # N_MIN EXPERIMENT
    # ========================================================

    for n_min in N_MINS:

        print("-" * 70)
        print(f"N_min = {n_min}")
        print("-" * 70)

        scorer = FuzzyRiskScorer(
            threshold=THRESHOLD,
            min_sample_size=n_min,
        )

        await scorer.load_fuzzy_configuration()

        predictions = []
        labels = []

        risk_values = []

        # ----------------------------------------------------
        # NORMAL WINDOWS
        # ----------------------------------------------------

        print("Testing normal windows...")

        for window_id in range(N_WINDOWS):

            records = generate_normal_window(
                n=n_min,
                seed=window_id,
            )

            result = scorer.score(
                records,
                FIELDS,
            )

            prediction = int(result.triggered)

            predictions.append(prediction)
            labels.append(0)

            risk_values.append(float(result.score))

        # ----------------------------------------------------
        # RISKY WINDOWS
        # ----------------------------------------------------

        print("Testing risky windows...")

        for window_id in range(N_WINDOWS):

            records = generate_risky_window(
                n=n_min,
                seed=window_id,
            )

            result = scorer.score(
                records,
                FIELDS,
            )

            prediction = int(result.triggered)

            predictions.append(prediction)
            labels.append(1)

            risk_values.append(float(result.score))

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        metrics = compute_metrics(
            predictions,
            labels,
        )

        row = {
            "N_min": n_min,

            "TP": metrics["TP"],
            "TN": metrics["TN"],
            "FP": metrics["FP"],
            "FN": metrics["FN"],

            "FPR": metrics["FPR"],
            "Recall": metrics["Recall"],
            "Precision": metrics["Precision"],
            "Accuracy": metrics["Accuracy"],

            "mean_risk": (
                sum(risk_values) / len(risk_values)
                if risk_values
                else 0.0
            ),
        }

        all_results.append(row)

        print()
        print(f"TP        = {row['TP']}")
        print(f"TN        = {row['TN']}")
        print(f"FP        = {row['FP']}")
        print(f"FN        = {row['FN']}")
        print(f"FPR       = {row['FPR']:.4f}")
        print(f"Recall    = {row['Recall']:.4f}")
        print(f"Precision = {row['Precision']:.4f}")
        print(f"Accuracy  = {row['Accuracy']:.4f}")
        print(f"Mean risk = {row['mean_risk']:.4f}")

    # ========================================================
    # SAVE CSV
    # ========================================================

    csv_path = RESULTS_DIR / "false_alerts.csv"

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "N_min",
                "TP",
                "TN",
                "FP",
                "FN",
                "FPR",
                "Recall",
                "Precision",
                "Accuracy",
                "mean_risk",
            ],
        )

        writer.writeheader()
        writer.writerows(all_results)

    print()
    print(f"CSV saved to: {csv_path}")

    # ========================================================
    # FPR PLOT
    # ========================================================

    x = [r["N_min"] for r in all_results]
    fpr = [r["FPR"] for r in all_results]

    plt.figure(figsize=(8, 5))

    plt.plot(
        x,
        fpr,
        marker="o",
    )

    plt.xlabel("Minimum sample size (N_min)")
    plt.ylabel("False Positive Rate")
    plt.title("False Positive Rate according to N_min")

    plt.xticks(N_MINS)
    plt.ylim(0, 1.05)

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    fpr_path = PLOTS_DIR / "false_alerts.png"

    plt.savefig(
        fpr_path,
        dpi=150,
    )

    plt.close()

    print(f"FPR plot saved to: {fpr_path}")

    # ========================================================
    # RECALL PLOT
    # ========================================================

    recall = [r["Recall"] for r in all_results]

    plt.figure(figsize=(8, 5))

    plt.plot(
        x,
        recall,
        marker="o",
    )

    plt.xlabel("Minimum sample size (N_min)")
    plt.ylabel("Recall")
    plt.title("Recall according to N_min")

    plt.xticks(N_MINS)
    plt.ylim(0, 1.05)

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    recall_path = PLOTS_DIR / "recall_vs_nmin.png"

    plt.savefig(
        recall_path,
        dpi=150,
    )

    plt.close()

    print(f"Recall plot saved to: {recall_path}")

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"{'N_min':>8}"
        f"{'TP':>6}"
        f"{'TN':>6}"
        f"{'FP':>6}"
        f"{'FN':>6}"
        f"{'FPR':>10}"
        f"{'Recall':>10}"
    )

    print("-" * 70)

    for r in all_results:

        print(
            f"{r['N_min']:>8}"
            f"{r['TP']:>6}"
            f"{r['TN']:>6}"
            f"{r['FP']:>6}"
            f"{r['FN']:>6}"
            f"{r['FPR']:>10.4f}"
            f"{r['Recall']:>10.4f}"
        )

    print()
    print("=" * 70)
    print("D.2 FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())