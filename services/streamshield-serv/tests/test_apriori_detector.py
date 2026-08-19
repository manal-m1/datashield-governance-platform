"""
StreamShield - Tests pour AprioriCombinationDetector (Tâche 2, étape 4)
Lancer avec : pytest tests/test_apriori_detector.py -v
"""
import pytest
from detection.risk_scorer import RiskScorer
from detection.apriori_detector import AprioriCombinationDetector, DetectionConfig


class TestPruningStopsExpansion:

    def test_no_risk_stays_at_level_1(self):
        """Aucune variation dans les données -> rien n'est étendu au-delà des champs seuls."""
        scorer = RiskScorer(threshold=0.5)
        config = DetectionConfig(candidate_fields=("ville", "sexe", "pays"), prune_threshold=0.15, max_depth=3)
        detector = AprioriCombinationDetector(scorer, config)

        records = [{"ville": "Rabat", "sexe": "M", "pays": "Maroc"}] * 30
        results = detector.detect(records)

        assert len(results) == 3  # seulement les 3 champs seuls, aucune extension
        assert all(not r.triggered for r in results)

    def test_risky_combination_gets_extended(self):
        """Un profil unique doit faire remonter le score dès le niveau 1 et déclencher une extension."""
        scorer = RiskScorer(threshold=0.5)
        config = DetectionConfig(candidate_fields=("ville", "sexe", "cin"), prune_threshold=0.1, max_depth=3)
        detector = AprioriCombinationDetector(scorer, config)

        records = [{"ville": "Rabat", "sexe": "M", "cin": f"AB{i:06d}"} for i in range(19)]
        records.append({"ville": "Agadir", "sexe": "F", "cin": "ZZ999999"})

        results = detector.detect(records)
        depths = {len(r.fields) for r in results}

        assert 1 in depths
        assert 2 in depths  # preuve que l'extension a eu lieu
        assert 3 in depths  # jusqu'à la combinaison complète


class TestMaxDepth:

    def test_never_exceeds_max_depth(self):
        scorer = RiskScorer(threshold=0.1)  # seuil bas -> tout risque de s'étendre
        config = DetectionConfig(
            candidate_fields=("a", "b", "c", "d", "e"), prune_threshold=0.01, max_depth=2
        )
        detector = AprioriCombinationDetector(scorer, config)

        records = [{"a": "x", "b": "y", "c": "z", "d": "w", "e": "v"}]  # tout unique -> tout risqué
        results = detector.detect(records)

        assert all(len(r.fields) <= 2 for r in results)


class TestTriggeredOnly:

    def test_triggered_only_filters_correctly(self):
        scorer = RiskScorer(threshold=0.5)
        config = DetectionConfig(candidate_fields=("ville", "sexe"), prune_threshold=0.1, max_depth=2)
        detector = AprioriCombinationDetector(scorer, config)

        records = [{"ville": "Rabat", "sexe": "M"}] * 19 + [{"ville": "Agadir", "sexe": "F"}]

        all_results = detector.detect(records)
        triggered = detector.triggered_only(records)

        assert len(triggered) <= len(all_results)
        assert all(r.triggered for r in triggered)


class TestNoDuplicateCandidates:

    def test_extension_does_not_duplicate_combinations(self):
        """('ville','sexe') étendu en cin ET ('ville','cin') étendu en sexe ne doivent
        pas produire deux fois la même combinaison ('ville','sexe','cin')."""
        scorer = RiskScorer(threshold=0.01)
        config = DetectionConfig(candidate_fields=("ville", "sexe", "cin"), prune_threshold=0.01, max_depth=3)
        detector = AprioriCombinationDetector(scorer, config)

        records = [{"ville": "Rabat", "sexe": "M", "cin": f"AB{i:06d}"} for i in range(5)]
        results = detector.detect(records)

        combos = [tuple(sorted(r.fields)) for r in results]
        assert len(combos) == len(set(combos))  # aucun doublon