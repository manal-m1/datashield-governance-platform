from detection.reference_risk_score import ReferenceRiskScorer


def test_reference_score_low_risk():

    records = [
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Lyon"},
        {"ville": "Lyon"},
        {"ville": "Lyon"},
    ]

    scorer = ReferenceRiskScorer(
        field_sensitivity={
            "ville": "low"
        }
    )

    score = scorer.score(
        records,
        ("ville",)
    )

    print("REFERENCE SCORE =", score)

    assert 0.0 <= score <= 1.0


def test_reference_score_high_risk():

    records = [
        {"date_naissance": "1990-01-01"},
        {"date_naissance": "1990-01-01"},
        {"date_naissance": "1990-01-01"},
        {"date_naissance": "2000-01-01"},
    ]

    scorer = ReferenceRiskScorer(
        field_sensitivity={
            "date_naissance": "high"
        }
    )

    score = scorer.score(
        records,
        ("date_naissance",)
    )

    print("REFERENCE SCORE =", score)

    assert 0.0 <= score <= 1.0
def test_reference_formula_does_not_use_k():

    scorer = ReferenceRiskScorer(
        field_sensitivity={
            "ville": "medium"
        }
    )

    records_a = [
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Lyon"},
        {"ville": "Lyon"},
    ]

    records_b = [
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Paris"},
        {"ville": "Paris"},
    ]

    score_a = scorer.score(
        records_a,
        ("ville",)
    )

    score_b = scorer.score(
        records_b,
        ("ville",)
    )

    print("SCORE A =", score_a)
    print("SCORE B =", score_b)

    # Les deux datasets ont :
    # uniqueness = 0
    # sensitivity = 0.5
    #
    # Le k est différent :
    # A -> k = 2
    # B -> k = 6
    #
    # Pourtant le score de référence doit être identique.

    assert score_a == score_b