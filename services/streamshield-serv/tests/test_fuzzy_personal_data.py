import pytest

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


PERSONAL_FIELDS = [
    "cin",
    "nom",
    "prenom",
    "date_naissance",
    "email",
    "telephone",
    "ville",
    "adresse",
    "code_postal",
    "passport",
    "iban",
    "carte_bancaire",
    "medical_condition",
    "numero_assurance",
]


def build_records():
    records = []

    for i in range(20):
        records.append({
            "cin": f"AB{i:06d}",
            "nom": f"Nom{i}",
            "prenom": f"Prenom{i}",
            "date_naissance": f"198{i % 10}-01-01",
            "email": f"user{i}@example.com",
            "telephone": f"06000000{i:02d}",
            "ville": "Casablanca",
            "adresse": f"Adresse {i}",
            "code_postal": "20000",
            "passport": f"P{i:07d}",
            "iban": f"MA000000000000000000000{i:02d}",
            "carte_bancaire": f"400000000000000{i:02d}",
            "medical_condition": "Aucune",
            "numero_assurance": f"ASS{i:08d}",
            "sexe": "F",
        })

    return records


@pytest.mark.parametrize(
    "fields",
    [
        ("cin",),
        ("nom",),
        ("prenom",),
        ("date_naissance",),
        ("email",),
        ("telephone",),
        ("ville",),
        ("adresse",),
        ("code_postal",),
        ("passport",),
        ("iban",),
        ("carte_bancaire",),
        ("medical_condition",),
        ("numero_assurance",),

        # Combinaisons
        ("nom", "prenom"),
        ("nom", "prenom", "date_naissance"),
        ("nom", "prenom", "date_naissance", "code_postal"),
        ("ville", "code_postal", "sexe"),
        ("email", "telephone"),
        ("cin", "date_naissance"),
        ("iban", "nom"),
        ("passport", "nom"),
    ],
)
def test_personal_field_combinations_produce_valid_score(fields):

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        min_sample_size=0,
    )

    records = build_records()

    result = scorer.score(records, fields)

    # Le score doit toujours être valide
    assert 0.0 <= result.score <= 1.0

    # Les métriques doivent être valides
    assert result.k >= 1
    assert 0.0 <= result.uniqueness <= 1.0
    assert 0.0 <= result.avg_sensitivity <= 1.0

    print(
        f"\nfields={fields}"
        f" | k={result.k}"
        f" | uniqueness={result.uniqueness:.3f}"
        f" | sensitivity={result.avg_sensitivity:.3f}"
        f" | score={result.score:.3f}"
        f" | triggered={result.triggered}"
    )