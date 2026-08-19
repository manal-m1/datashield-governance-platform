"""
StreamShield - Tests pour CombinationAnalyzer (Tâche 2, étape 2)
Lancer avec : pytest tests/test_frequency_counter.py -v
"""
import pytest
from detection.frequency_counter import CombinationAnalyzer


class TestComputeK:

    def test_unique_combination_gives_k_1(self):
        """Un profil totalement unique doit donner k=1 -- le pire cas de risque."""
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Agadir", "sexe": "M"},  # unique
        ]
        k = CombinationAnalyzer.compute_k(records, ("ville", "sexe"))
        assert k == 1

    def test_shared_combination_gives_higher_k(self):
        """3 individus partagent exactement la même combinaison -> k=3."""
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
        ]
        k = CombinationAnalyzer.compute_k(records, ("ville", "sexe"))
        assert k == 3

    def test_k_is_the_minimum_across_all_groups(self):
        """k(C) doit être le MINIMUM sur toutes les classes d'équivalence, pas la moyenne."""
        records = [
            {"ville": "Rabat", "sexe": "M"},       # x5, grand groupe
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Agadir", "sexe": "F"},       # x1, groupe unique
        ]
        k = CombinationAnalyzer.compute_k(records, ("ville", "sexe"))
        assert k == 1  # pas 3 (la moyenne), le minimum

    def test_empty_records_gives_k_0(self):
        k = CombinationAnalyzer.compute_k([], ("ville", "sexe"))
        assert k == 0

    def test_missing_field_excludes_record(self):
        """Un enregistrement incomplet pour la combinaison C ne doit pas fausser k(C)."""
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat"},  # champ 'sexe' manquant -> ignoré
        ]
        k = CombinationAnalyzer.compute_k(records, ("ville", "sexe"))
        assert k == 1  # un seul enregistrement complet, donc k=1 (pas d'erreur, pas de faux 2)

    def test_none_value_excludes_record(self):
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": None},
        ]
        k = CombinationAnalyzer.compute_k(records, ("ville", "sexe"))
        assert k == 1


class TestComputeUniqueness:

    def test_all_unique_gives_uniqueness_1(self):
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Agadir", "sexe": "F"},
            {"ville": "Fes", "sexe": "M"},
        ]
        u = CombinationAnalyzer.compute_uniqueness(records, ("ville", "sexe"))
        assert u == 1.0

    def test_no_unique_gives_uniqueness_0(self):
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
        ]
        u = CombinationAnalyzer.compute_uniqueness(records, ("ville", "sexe"))
        assert u == 0.0

    def test_partial_uniqueness(self):
        """8 enregistrements communs + 1 unique -> 1/9 sont uniques."""
        records = [{"ville": "Rabat", "sexe": "M"}] * 8 + [{"ville": "Agadir", "sexe": "F"}]
        u = CombinationAnalyzer.compute_uniqueness(records, ("ville", "sexe"))
        assert u == pytest.approx(1 / 9)

    def test_empty_records_gives_uniqueness_0(self):
        u = CombinationAnalyzer.compute_uniqueness([], ("ville", "sexe"))
        assert u == 0.0


class TestAnalyze:

    def test_analyze_matches_individual_methods(self):
        """analyze() doit donner le même résultat que compute_k + compute_uniqueness séparés."""
        records = [
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Rabat", "sexe": "M"},
            {"ville": "Agadir", "sexe": "F"},
        ]
        fields = ("ville", "sexe")
        result = CombinationAnalyzer.analyze(records, fields)

        assert result["k"] == CombinationAnalyzer.compute_k(records, fields)
        assert result["uniqueness"] == CombinationAnalyzer.compute_uniqueness(records, fields)
        assert result["sample_size"] == 3
        assert result["fields"] == fields

    def test_analyze_empty_records(self):
        result = CombinationAnalyzer.analyze([], ("ville", "sexe"))
        assert result == {"fields": ("ville", "sexe"), "k": 0, "uniqueness": 0.0, "sample_size": 0}

    def test_single_field_combination(self):
        """Doit aussi fonctionner avec un seul champ (pas seulement des paires)."""
        records = [
            {"ville": "Rabat"},
            {"ville": "Rabat"},
            {"ville": "Agadir"},
        ]
        result = CombinationAnalyzer.analyze(records, ("ville",))
        assert result["k"] == 1  # Agadir est unique