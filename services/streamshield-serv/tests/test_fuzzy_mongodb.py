import asyncio

from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.field_sensitivity_repository import load_field_sensitivity


async def main():

    print("=" * 70)
    print("TEST FUZZY RISK SCORER + MONGODB")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. Charger les sensibilités depuis MongoDB
    # ------------------------------------------------------------

    field_sensitivity = await load_field_sensitivity()

    print("\n[1] FIELD SENSITIVITY")
    print(f"Nombre de champs chargés : {len(field_sensitivity)}")
    print(field_sensitivity)

    # ------------------------------------------------------------
    # 2. Créer le scorer
    # ------------------------------------------------------------

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity=field_sensitivity,
    )

    # ------------------------------------------------------------
    # 3. Charger fuzzy_config + fuzzy_rules depuis MongoDB
    # ------------------------------------------------------------

    await scorer.load_fuzzy_configuration()

    print("\n[2] FUZZY CONFIG")
    print(
        "Sections disponibles :",
        list(scorer.fuzzy_config.keys())
    )

    print(
        "K fuzzy sets :",
        list(scorer.fuzzy_config["k_fuzzy_sets"].keys())
    )

    print(
        "Uniqueness fuzzy sets :",
        list(scorer.fuzzy_config["uniqueness_fuzzy_sets"].keys())
    )

    print(
        "Sensitivity fuzzy sets :",
        list(scorer.fuzzy_config["sensitivity_fuzzy_sets"].keys())
    )

    print(
        "Output levels :",
        scorer.fuzzy_config["output_levels"]
    )

    print(
        "Min sample size :",
        scorer.min_sample_size
    )

    print("\n[3] FUZZY RULES")
    print(f"Nombre de règles chargées : {len(scorer.fuzzy_rules)}")

    for rule in scorer.fuzzy_rules:
        print(
            f"{rule.get('_id', 'no-id')} -> "
            f"{rule.get('name', 'no-name')} -> "
            f"{rule.get('output')}"
        )

    # ------------------------------------------------------------
    # 4. Données de test
    # ------------------------------------------------------------
    #
    # 20 lignes identiques => k = 20
    # donc :
    #   k fuzzy "faible" = 1
    #   uniqueness faible = 1
    #
    # Cela doit déclencher R8 :
    #   k faible + unicité faible -> faible
    #
    # donc score attendu = output_levels["faible"]
    # normalement 0.15
    # ------------------------------------------------------------

    records = []

    for i in range(20):
        records.append({
            "ville": "Rabat",
            "code_postal": "10000",
            "sexe": "F",
            "date_naissance": "2000-01-01",
        })

    fields = (
        "ville",
        "code_postal",
        "sexe",
        "date_naissance",
    )

    print("\n[4] DONNEES")
    print(f"Nombre de records : {len(records)}")
    print(f"Fields : {fields}")

    # ------------------------------------------------------------
    # 5. Calcul du score
    # ------------------------------------------------------------

    result = scorer.score(
        records,
        fields,
    )

    print("\n[5] RESULTAT")
    print("fields           =", result.fields)
    print("k                =", result.k)
    print("uniqueness       =", result.uniqueness)
    print("avg_sensitivity  =", result.avg_sensitivity)
    print("score            =", result.score)
    print("triggered        =", result.triggered)
    print("sample_size      =", result.sample_size)

    # ------------------------------------------------------------
    # 6. Vérifications automatiques
    # ------------------------------------------------------------

    assert scorer.fuzzy_config is not None
    assert len(scorer.fuzzy_rules) > 0
    assert len(field_sensitivity) > 0

    assert result.sample_size == 20
    assert result.k == 20

    print("\n[6] TESTS")
    print("OK : configuration fuzzy chargée depuis MongoDB")
    print("OK : règles fuzzy chargées depuis MongoDB")
    print("OK : sensibilités chargées depuis MongoDB")
    print("OK : k calculé")
    print("OK : score calculé")

    expected_low_score = scorer.fuzzy_config["output_levels"]["faible"]

    print(
        f"\nScore attendu selon MongoDB "
        f"(output_levels['faible']) = {expected_low_score}"
    )

    assert abs(result.score - expected_low_score) < 1e-9

    print(
        f"OK : score réel {result.score} "
        f"== score MongoDB {expected_low_score}"
    )

    print("\n" + "=" * 70)
    print("TEST REUSSI")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())