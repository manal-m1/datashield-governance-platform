from detection.fuzzy_risk_scorer import FuzzyRiskScorer


def test_missing_field():

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity={
            "ville": "low",
            "code_postal": "medium",
        },
    )

    # "champ_inexistant" n'est pas présent
    fields = (
        "ville",
        "champ_inexistant",
    )

    score = scorer._average_sensitivity(fields)

    print("Average sensitivity =", score)

    # ville = low = 0.2
    # champ_inexistant = medium = 0.5
    # moyenne = 0.35
    assert score == 0.35
def test_invalid_sensitivity():

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity={
            "ville": "very_high",
        },
    )

    score = scorer._average_sensitivity(
        ("ville",)
    )

    print("Average sensitivity =", score)

    # very_high est invalide
    # fallback medium = 0.5
    assert score == 0.5