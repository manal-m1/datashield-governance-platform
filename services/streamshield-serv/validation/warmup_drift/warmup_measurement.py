
"""
D.1 - Warm-up measurement for StreamShield.

Measures:
    N = sample size
    k = minimum equivalence-class size
    u = uniqueness
    R = fuzzy risk score

The experiment uses the production FuzzyRiskScorer configuration
loaded from MongoDB, but does NOT modify the production consumer.

Output:
    validation/warmup_drift/results/warmup.csv
    validation/warmup_drift/plots/warmup_k.png
    validation/warmup_drift/plots/warmup_u.png
    validation/warmup_drift/plots/warmup_risk.png
"""

import asyncio
import csv
import os
import random
import sys
from datetime import datetime

import matplotlib.pyplot as plt

# Allow imports from services/streamshield-serv
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../.."
)))

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


FIELDS = ("ville", "sexe")

N_MIN = 20

OUTPUT_CSV = os.path.join(
    os.path.dirname(__file__),
    "results",
    "warmup.csv",
)

PLOT_DIR = os.path.join(
    os.path.dirname(__file__),
    "plots",
)


def generate_records(n: int):
    """
    Generate a controlled dataset.

    We intentionally create repeated combinations so that
    k and uniqueness evolve as the sample grows.
    """

    villes = [
        "Casablanca",
        "Rabat",
        "Marrakech",
        "Fes",
        "Tanger",
    ]

    sexes = ["M", "F"]

    records = []

    for i in range(n):
        # Repeated structure with some diversity.
        # This allows k and uniqueness to evolve.
        ville = villes[i % len(villes)]
        sexe = sexes[(i // 2) % len(sexes)]

        records.append({
            "ville": ville,
            "sexe": sexe,
        })

    return records


async def main():

    print("=" * 70)
    print("STREAMSHIELD - D.1 WARM-UP MEASUREMENT")
    print("=" * 70)

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)

    # Production fuzzy scorer.
    scorer = FuzzyRiskScorer(
        threshold=0.7,
        min_sample_size=N_MIN,
    )

    # Load the current fuzzy configuration from MongoDB.
    await scorer.load_fuzzy_configuration()

    print()
    print("Fuzzy configuration loaded.")
    print(f"Threshold       : {scorer.threshold}")
    print(f"N_min           : {scorer.min_sample_size}")
    print(f"Fields          : {FIELDS}")
    print()

    rows = []

    # Start from a small sample and progressively increase it.
    sample_sizes = list(range(1, 101))

    for n in sample_sizes:

        records = generate_records(n)

        result = scorer.score(
            records,
            FIELDS,
        )

        row = {
            "timestamp": datetime.now().isoformat(),
            "sample_size": n,
            "k": result.k,
            "uniqueness": result.uniqueness,
            "risk": result.score,
            "triggered": result.triggered,
        }

        rows.append(row)

        print(
            f"N={n:3d} | "
            f"k={result.k:3d} | "
            f"u={result.uniqueness:.4f} | "
            f"R={result.score:.4f} | "
            f"triggered={result.triggered}"
        )

    # ------------------------------------------------------------------
    # Save CSV
    # ------------------------------------------------------------------

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "sample_size",
                "k",
                "uniqueness",
                "risk",
                "triggered",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"CSV saved to: {OUTPUT_CSV}")

    # ------------------------------------------------------------------
    # Plot k
    # ------------------------------------------------------------------

    x = [r["sample_size"] for r in rows]
    k_values = [r["k"] for r in rows]

    plt.figure(figsize=(10, 5))
    plt.plot(x, k_values, marker="o", markersize=2)
    plt.axvline(
        N_MIN,
        linestyle="--",
        label=f"N_min = {N_MIN}",
    )
    plt.xlabel("Sample size N")
    plt.ylabel("k(C)")
    plt.title("Warm-up evolution of k(C)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    path_k = os.path.join(
        PLOT_DIR,
        "warmup_k.png",
    )

    plt.savefig(path_k, dpi=150)
    plt.close()

    # ------------------------------------------------------------------
    # Plot uniqueness
    # ------------------------------------------------------------------

    u_values = [r["uniqueness"] for r in rows]

    plt.figure(figsize=(10, 5))
    plt.plot(x, u_values, marker="o", markersize=2)
    plt.axvline(
        N_MIN,
        linestyle="--",
        label=f"N_min = {N_MIN}",
    )
    plt.xlabel("Sample size N")
    plt.ylabel("Uniqueness u(C)")
    plt.title("Warm-up evolution of uniqueness")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    path_u = os.path.join(
        PLOT_DIR,
        "warmup_u.png",
    )

    plt.savefig(path_u, dpi=150)
    plt.close()

    # ------------------------------------------------------------------
    # Plot risk
    # ------------------------------------------------------------------

    risk_values = [r["risk"] for r in rows]

    plt.figure(figsize=(10, 5))
    plt.plot(x, risk_values, marker="o", markersize=2)
    plt.axvline(
        N_MIN,
        linestyle="--",
        label=f"N_min = {N_MIN}",
    )
    plt.axhline(
        scorer.threshold,
        linestyle=":",
        label=f"Threshold = {scorer.threshold}",
    )
    plt.xlabel("Sample size N")
    plt.ylabel("Risk score R")
    plt.title("Warm-up evolution of fuzzy risk score")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    path_r = os.path.join(
        PLOT_DIR,
        "warmup_risk.png",
    )

    plt.savefig(path_r, dpi=150)
    plt.close()

    print()
    print("Plots generated:")
    print(f"  {path_k}")
    print(f"  {path_u}")
    print(f"  {path_r}")

    print()
    print("=" * 70)
    print("D.1 FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())