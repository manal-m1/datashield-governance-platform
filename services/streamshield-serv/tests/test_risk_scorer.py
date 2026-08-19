"""
StreamShield - Tests pour RiskScorer (Tâche 2, étape 3)
Lancer avec : pytest tests/test_risk_scorer.py -v
"""
import pytest
from detection.risk_scorer import RiskScorer, RiskWeights


class TestScoreBasics:

    def test_common_combination_does_not_trigger(self):
        """20 personnes partagent exactement la même combinaison peu sensible -> pas d'alerte."""
        scorer = RiskScorer(threshold=0.5)
        records = [{"ville": "Rabat", "sexe": "M"}] * 20
        result = scorer.score(records, ("ville", "sexe"))
        assert result.k == 20
        assert result.triggered is False

    def test_unique_sensitive_combination_triggers(self):
        """Un profil unique combiné à un champ critique (cin) -> alerte."""
        scorer = RiskScorer(threshold=0.5)
        records = [{"ville": "Rabat", "sexe": "M", "cin": f"AB{i:06d}"} for i in range(19)]
        records.append({"ville": "Agadir", "sexe": "F", "cin": "ZZ999999"})
        result = scorer.score(records, ("ville", "sexe", "cin"))
        assert result.k == 1
        assert result.triggered is True

    def test_empty_combination_gives_zero_score_not_triggered(self):
        """Champ absent de tous les enregistrements -> k=0, score=0, pas d'alerte (pas d'erreur)."""
        scorer = RiskScorer(threshold=0.5)
        records = [{"ville": "Rabat"}] * 5  # pas de champ 'cin'
        result = scorer.score(records, ("ville", "cin"))
        assert result.k == 0
        assert result.score == 0.0
        assert result.triggered is False

    def test_no_division_by_zero_error(self):
        """S'assure explicitement qu'aucune exception n'est levée sur une fenêtre vide."""
        scorer = RiskScorer()
        result = scorer.score([], ("ville", "sexe"))
        assert result.score == 0.0


class TestScoreBounds:

    def test_score_never_exceeds_one(self):
        """Même avec des poids déséquilibrés, le score doit rester borné à 1.0."""
        scorer = RiskScorer(weights=RiskWeights(w1=2.0, w2=2.0, w3=2.0), threshold=0.5)
        records = [{"ville": "Agadir", "sexe": "F", "cin": "UNIQUE01"}]
        result = scorer.score(records, ("ville", "sexe", "cin"))
        assert result.score <= 1.0

    def test_score_never_negative(self):
        scorer = RiskScorer(weights=RiskWeights(w1=0.0, w2=0.0, w3=0.0), threshold=0.5)
        records = [{"ville": "Rabat", "sexe": "M"}] * 5
        result = scorer.score(records, ("ville", "sexe"))
        assert result.score >= 0.0


class TestThreshold:

    def test_lower_threshold_triggers_more_easily(self):
        """La même donnée doit déclencher avec un seuil bas mais pas avec un seuil haut."""
        records = [{"ville": "Rabat", "sexe": "M"}] * 10 + [{"ville": "Agadir", "sexe": "F"}]

        strict_scorer = RiskScorer(threshold=0.9)
        lenient_scorer = RiskScorer(threshold=0.1)

        strict_result = strict_scorer.score(records, ("ville", "sexe"))
        lenient_result = lenient_scorer.score(records, ("ville", "sexe"))

        assert strict_result.score == lenient_result.score  # même score calculé
        assert lenient_result.triggered is True
        assert strict_result.triggered is False


class TestFieldSensitivity:

    def test_custom_sensitivity_map_changes_score(self):
        """Un champ reclassé 'critical' au lieu de 'low' doit augmenter le score."""
        records = [{"ville": "Rabat", "sexe": "M"}] * 10 + [{"ville": "Agadir", "sexe": "F"}]

        low_sensitivity_scorer = RiskScorer(field_sensitivity={"ville": "low", "sexe": "low"})
        high_sensitivity_scorer = RiskScorer(field_sensitivity={"ville": "critical", "sexe": "critical"})

        low_result = low_sensitivity_scorer.score(records, ("ville", "sexe"))
        high_result = high_sensitivity_scorer.score(records, ("ville", "sexe"))

        assert high_result.score > low_result.score

    def test_unknown_field_defaults_to_medium(self):
        """Un champ non listé dans la table de sensibilité doit utiliser 'medium' par défaut, sans planter."""
        scorer = RiskScorer(field_sensitivity={})
        records = [{"champ_inconnu": "valeur"}] * 5
        result = scorer.score(records, ("champ_inconnu",))
        assert result.avg_sensitivity == pytest.approx(0.5)