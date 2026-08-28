from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.combination_detector import (
    CombinationDetector,
    DetectionConfig,
)


def test_combination_detector():

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity={
            "ville": "low",
            "sexe": "low",
            "date_naissance": "high",
        },
        min_sample_size=1,
    )

    detector = CombinationDetector(
        scorer,
        DetectionConfig(
            candidate_fields=(
                "ville",
                "sexe",
                "date_naissance",
            ),
            max_depth=3,
        ),
    )

    records = [
        {
            "ville": "Rabat",
            "sexe": "F",
            "date_naissance": "2000-01-01",
        },
        {
            "ville": "Rabat",
            "sexe": "F",
            "date_naissance": "2000-01-01",
        },
        {
            "ville": "Rabat",
            "sexe": "M",
            "date_naissance": "1999-05-10",
        },
    ]

    results = detector.detect(records)

    print(f"Nombre de combinaisons testées : {len(results)}")

    for result in results:
        print(result)

    assert len(results) == 7