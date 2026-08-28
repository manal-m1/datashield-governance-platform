import asyncio

from detection.field_sensitivity_repository import load_field_sensitivity
from detection.fuzzy_risk_scorer import FuzzyRiskScorer


async def main():

    # 1. Charger MongoDB
    sensitivity = await load_field_sensitivity()

    print("=== SENSIBILITES CHARGEES ===")

    for field, level in sensitivity.items():
        print(f"{field} -> {level}")

    # 2. Créer le scorer avec les sensibilités MongoDB
    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity=sensitivity,
    )

    # 3. Vérifier directement la sensibilité moyenne
    combinations = [
        ("ville", "sexe"),
        ("ville", "sexe", "date_naissance"),
        ("cin", "nom"),
        ("email", "ville"),
    ]

    print("\n=== SENSIBILITE MOYENNE ===")

    for fields in combinations:
        avg = scorer._average_sensitivity(fields)

        print(
            f"{fields} -> "
            f"avg_sensitivity={avg:.4f}"
        )


if __name__ == "__main__":
    asyncio.run(main())