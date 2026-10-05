import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


FIELDS = ("ville", "sexe")


def generate_d1_records(n):
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
        ville = villes[i % len(villes)]
        sexe = sexes[(i // 2) % len(sexes)]

        records.append({
            "ville": ville,
            "sexe": sexe,
        })

    return records


def generate_d2_records(n):
    records = []

    half = n // 2

    for i in range(half):
        records.append({
            "event_id": f"A-{i}",
            "ville": "Casablanca",
            "sexe": "M",
        })

    for i in range(n - half):
        records.append({
            "event_id": f"B-{i}",
            "ville": "Rabat",
            "sexe": "F",
        })

    return records


async def main():

    scorer = FuzzyRiskScorer(
        threshold=0.7,
        min_sample_size=20,
    )

    await scorer.load_fuzzy_configuration()

    d1 = generate_d1_records(20)
    d2 = generate_d2_records(20)

    print("=" * 70)
    print("D1 DATASET")
    print("=" * 70)

    print("Records:")
    for r in d1:
        print(r)

    result_d1 = scorer.score(d1, FIELDS)

    print()
    print("D1 RESULT")
    print(f"k              = {result_d1.k}")
    print(f"uniqueness     = {result_d1.uniqueness}")
    print(f"sensitivity    = {result_d1.avg_sensitivity}")
    print(f"sample_size    = {result_d1.sample_size}")
    print(f"risk           = {result_d1.score}")
    print(f"triggered      = {result_d1.triggered}")

    print()
    print("=" * 70)
    print("D2 DATASET")
    print("=" * 70)

    print("Records:")
    for r in d2:
        print(r)

    result_d2 = scorer.score(d2, FIELDS)

    print()
    print("D2 RESULT")
    print(f"k              = {result_d2.k}")
    print(f"uniqueness     = {result_d2.uniqueness}")
    print(f"sensitivity    = {result_d2.avg_sensitivity}")
    print(f"sample_size    = {result_d2.sample_size}")
    print(f"risk           = {result_d2.score}")
    print(f"triggered      = {result_d2.triggered}")


if __name__ == "__main__":
    asyncio.run(main())