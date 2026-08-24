import pytest

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


FIELDS = (
    "ville",
    "code_postal",
    "sexe",
    "date_naissance",
)


def build_records(k: int):
    """
    Construit un jeu de données contenant exactement
    une combinaison répétée k fois.
    """
    target = {
        "ville": "Casablanca",
        "code_postal": "20500",
        "sexe": "F",
        "date_naissance": "1985-07-22",
    }

    return [dict(target) for _ in range(k)]


def test_score_monotonicity_with_k():
    """
    Vérifie que le score de risque ne augmente jamais
    lorsque k augmente.

    Propriété attendue :

        score(k+1) <= score(k)

    Cette propriété garantit que l'augmentation de
    l'anonymat (k) entraîne une diminution ou une
    stabilisation du risque.
    """

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        min_sample_size=0,
    )

    scores = {}

    for k in range(1, 21):

        records = build_records(k)

        result = scorer.score(
            records,
            FIELDS,
        )

        scores[k] = result.score

        print(
            f"k={k:2d} | "
            f"score={result.score:.3f} | "
            f"uniqueness={result.uniqueness:.3f}"
        )

    # Vérification de monotonie
    for k in range(1, 20):

        current_score = scores[k]
        next_score = scores[k + 1]

        assert next_score <= current_score, (
            f"Violation de monotonie détectée : "
            f"k={k} → score={current_score:.3f}, "
            f"k={k + 1} → score={next_score:.3f}. "
            f"Le score ne doit pas augmenter lorsque k augmente."
        )


def test_low_risk_cases_are_not_critical():
    """
    Vérifie que les valeurs élevées de k ne produisent
    pas un score critique.

    Dans notre modèle :
        k >= 7 correspond à un risque faible.
    """

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        min_sample_size=0,
    )

    for k in [7, 8, 10, 15, 20]:

        records = build_records(k)

        result = scorer.score(
            records,
            FIELDS,
        )

        print(
            f"k={k:2d} | score={result.score:.3f}"
        )

        assert result.score < 0.70, (
            f"Cas à faible risque classé comme élevé/critique : "
            f"k={k}, score={result.score:.3f}"
        )


def test_high_risk_cases_have_higher_scores():
    """
    Vérifie que les petits k produisent des scores
    supérieurs aux grands k.
    """

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        min_sample_size=0,
    )

    result_k1 = scorer.score(
        build_records(1),
        FIELDS,
    )

    result_k10 = scorer.score(
        build_records(10),
        FIELDS,
    )

    result_k20 = scorer.score(
        build_records(20),
        FIELDS,
    )

    assert result_k1.score > result_k10.score
    assert result_k10.score >= result_k20.score