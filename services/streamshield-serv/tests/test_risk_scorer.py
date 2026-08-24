"""
StreamShield - Tests pour FuzzyRiskScorer (Tâche 2, étape 3)

Lancer avec :
    pytest tests/test_risk_scorer.py -v
"""

import pytest

from detection.fuzzy_risk_scorer import FuzzyRiskScorer


# ============================================================================
# SCORE BASICS
# ============================================================================

class TestScoreBasics:

    def test_common_combination_does_not_trigger(self):
        """
        Une combinaison partagée par 20 personnes ne doit pas être considérée
        comme risquée.

        k = 20 -> risque faible -> score faible.
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=0,
        )

        records = [
            {"ville": "Rabat", "sexe": "M"}
            for _ in range(20)
        ]

        result = scorer.score(
            records,
            ("ville", "sexe"),
        )

        assert result.k == 20
        assert 0.0 <= result.score <= 1.0
        assert result.triggered is False


    def test_unique_sensitive_combination_triggers(self):
        """
        Une combinaison unique avec un champ fortement sensible
        doit générer un score élevé et déclencher une alerte.

        k = 1 -> risque critique.
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=0,
            field_sensitivity={
                "ville": "low",
                "sexe": "low",
                "cin": "critical",
            },
        )

        records = [
            {
                "ville": "Rabat",
                "sexe": "M",
                "cin": f"AB{i:06d}",
            }
            for i in range(19)
        ]

        records.append({
            "ville": "Agadir",
            "sexe": "F",
            "cin": "ZZ999999",
        })

        result = scorer.score(
            records,
            ("ville", "sexe", "cin"),
        )

        assert result.k == 1
        assert result.score >= 0.5
        assert result.triggered is True


    def test_empty_combination_gives_zero_score_not_triggered(self):
        """
        Si les champs demandés ne permettent pas de construire une
        combinaison valide, k=0 et le score doit être nul.
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=0,
        )

        records = [
            {"ville": "Rabat"}
            for _ in range(5)
        ]

        result = scorer.score(
            records,
            ("ville", "cin"),
        )

        assert result.k == 0
        assert result.score == 0.0
        assert result.triggered is False


    def test_no_division_by_zero_error(self):
        """
        Une fenêtre vide ne doit provoquer aucune exception.
        """
        scorer = FuzzyRiskScorer(
            min_sample_size=0,
        )

        result = scorer.score(
            [],
            ("ville", "sexe"),
        )

        assert result.score == 0.0
        assert result.triggered is False


# ============================================================================
# SCORE BOUNDS
# ============================================================================

class TestScoreBounds:

    def test_score_always_within_bounds(self):
        """
        Le score fuzzy doit toujours appartenir à [0,1].
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=0,
        )

        records = [
            {"ville": "Casablanca", "sexe": "F"}
            for _ in range(30)
        ]

        result = scorer.score(
            records,
            ("ville", "sexe"),
        )

        assert 0.0 <= result.score <= 1.0


    def test_threshold_must_be_between_zero_and_one(self):
        """
        Le seuil doit être compris entre 0 et 1.
        """
        with pytest.raises(ValueError):
            FuzzyRiskScorer(threshold=-0.1)

        with pytest.raises(ValueError):
            FuzzyRiskScorer(threshold=1.1)


    def test_valid_threshold_is_accepted(self):
        """
        Les seuils valides doivent être acceptés.
        """
        FuzzyRiskScorer(threshold=0.0)
        FuzzyRiskScorer(threshold=0.5)
        FuzzyRiskScorer(threshold=1.0)


# ============================================================================
# THRESHOLD
# ============================================================================

class TestThreshold:

    def test_lower_threshold_triggers_more_easily(self):
        """
        Un seuil plus faible doit déclencher plus facilement une alerte.

        Le score calculé doit être identique : seul le seuil change.
        """
        records = (
            [{"ville": "Rabat", "sexe": "M"} for _ in range(10)]
            + [{"ville": "Agadir", "sexe": "F"}]
        )

        strict_scorer = FuzzyRiskScorer(
            threshold=0.9,
            min_sample_size=0,
        )

        lenient_scorer = FuzzyRiskScorer(
            threshold=0.1,
            min_sample_size=0,
        )

        strict_result = strict_scorer.score(
            records,
            ("ville", "sexe"),
        )

        lenient_result = lenient_scorer.score(
            records,
            ("ville", "sexe"),
        )

        # Le score fuzzy ne dépend pas du seuil.
        assert strict_result.score == pytest.approx(
            lenient_result.score
        )

        # Le seuil faible doit être plus facile à atteindre.
        assert (
            lenient_result.triggered
            or not strict_result.triggered
        )


# ============================================================================
# FIELD SENSITIVITY
# ============================================================================

class TestFieldSensitivity:

    def test_custom_sensitivity_is_used(self):
        """
        Vérifie que la sensibilité des champs est correctement prise
        en compte dans le calcul de avg_sensitivity.
        """
        records = [
            {"ville": "Rabat", "sexe": "M"}
            for _ in range(20)
        ]

        low_sensitivity_scorer = FuzzyRiskScorer(
            field_sensitivity={
                "ville": "low",
                "sexe": "low",
            },
            min_sample_size=0,
        )

        high_sensitivity_scorer = FuzzyRiskScorer(
            field_sensitivity={
                "ville": "critical",
                "sexe": "critical",
            },
            min_sample_size=0,
        )

        low_result = low_sensitivity_scorer.score(
            records,
            ("ville", "sexe"),
        )

        high_result = high_sensitivity_scorer.score(
            records,
            ("ville", "sexe"),
        )

        assert high_result.avg_sensitivity > low_result.avg_sensitivity


    def test_unknown_field_defaults_to_medium(self):
        """
        Un champ absent de la configuration doit utiliser
        la sensibilité 'medium' par défaut, soit 0.5.
        """
        scorer = FuzzyRiskScorer(
            field_sensitivity={},
            min_sample_size=0,
        )

        records = [
            {"champ_inconnu": "valeur"}
            for _ in range(5)
        ]

        result = scorer.score(
            records,
            ("champ_inconnu",),
        )

        assert result.avg_sensitivity == pytest.approx(0.5)


# ============================================================================
# MINIMUM SAMPLE SIZE
# ============================================================================

class TestMinimumSampleSize:

    def test_insufficient_sample_returns_zero_score(self):
        """
        Si le nombre d'enregistrements est inférieur au minimum requis,
        le score doit être nul et aucune alerte ne doit être déclenchée.
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=20,
        )

        records = [
            {"ville": "Rabat", "sexe": "M"}
            for _ in range(10)
        ]

        result = scorer.score(
            records,
            ("ville", "sexe"),
        )

        assert result.sample_size == 10
        assert result.score == 0.0
        assert result.triggered is False


    def test_sufficient_sample_is_processed(self):
        """
        Lorsque la taille minimale est atteinte, le calcul fuzzy
        doit être effectué normalement.
        """
        scorer = FuzzyRiskScorer(
            threshold=0.5,
            min_sample_size=20,
        )

        records = [
            {"ville": "Rabat", "sexe": "M"}
            for _ in range(20)
        ]

        result = scorer.score(
            records,
            ("ville", "sexe"),
        )

        assert result.sample_size == 20
        assert result.k == 20
        assert result.score >= 0.0