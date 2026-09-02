from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.reference_risk_score import ReferenceRiskScorer


def test_fuzzy_vs_reference():

    records = [
        {
            "ville": "Paris",
            "code_postal": "75001",
            "sexe": "F",
            "date_naissance": "1990-01-01",
        },
        {
            "ville": "Paris",
            "code_postal": "75001",
            "sexe": "F",
            "date_naissance": "1990-01-01",
        },
        {
            "ville": "Lyon",
            "code_postal": "69001",
            "sexe": "M",
            "date_naissance": "1985-05-10",
        },
        {
            "ville": "Rabat",
            "code_postal": "10000",
            "sexe": "F",
            "date_naissance": "1992-03-20",
        },
    ]

    fields = (
        "ville",
        "code_postal",
        "sexe",
        "date_naissance",
    )

    sensitivity = {
        "ville": "low",
        "code_postal": "medium",
        "sexe": "low",
        "date_naissance": "high",
    }

    reference = ReferenceRiskScorer(
        field_sensitivity=sensitivity
    )

    reference_score = reference.score(
        records,
        fields
    )

    print("REFERENCE SCORE =", reference_score)

    assert 0.0 <= reference_score <= 1.0