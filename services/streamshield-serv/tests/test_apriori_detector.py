"""
StreamShield - Tests unitaires du RiskScorer
"""
import pytest

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


def test_echantillon_trop_petit_non_declenche():
    """
    Un échantillon de 1 enregistrement ne doit jamais déclencher, même si
    k=1 et Unicité=1.0 trivialement -- régression identifiée en production
    (déclenchement mixte à 15s tirant une détection avec sample_size=1,
    score=0.84, alors qu'aucun signal statistique réel n'existe).
    """
    scorer = FuzzyRiskScorer(threshold=0.5)
    records = [{
        "ville": "Casablanca",
        "code_postal": "20500",
        "sexe": "F",
        "date_naissance": "1985-07-22",
    }]
    result = scorer.score(records, ("ville", "code_postal", "sexe", "date_naissance"))

    assert result.triggered is False
    assert result.score == 0.0
    assert result.k == 1  # k reste calculé correctement, juste pas exploité
    assert result.sample_size == 1


def test_echantillon_suffisant_peut_declencher():
    """Vérifie que le garde-fou ne bloque pas les cas légitimes une fois
    le seuil min_sample_size atteint."""
    scorer = FuzzyRiskScorer(threshold=0.5)
    records = []
    # 1 enregistrement unique + 25 de bruit -> sample_size=26, au-dessus du seuil
    records.append({
        "ville": "Casablanca", "code_postal": "20500",
        "sexe": "F", "date_naissance": "1985-07-22",
    })
    for i in range(25):
        records.append({
            "ville": f"ville_{i}", "code_postal": f"{10000+i}",
            "sexe": "M" if i % 2 else "F", "date_naissance": f"1990-01-0{i%9+1}",
        })

    result = scorer.score(records, ("ville", "code_postal", "sexe", "date_naissance"))

    assert result.sample_size == 26
    assert result.k == 1
    assert result.triggered is True  # doit pouvoir déclencher avec un échantillon suffisant