"""
StreamShield - Tâche 2, étape 4
Génération des combinaisons candidates (algorithme type Apriori adapté au
streaming, section 4.4 du cahier des charges).

Principe : au lieu de tester toutes les combinaisons possibles de champs à
chaque fenêtre (combinatoirement explosif), on part des champs seuls, et on
n'étend une combinaison que si elle a déjà dépassé un seuil de risque
minimal à l'étape précédente -- exactement la propriété d'élagage Apriori
("si une sous-combinaison n'est pas à risque, ses extensions ne le seront
presque jamais").
"""
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Tuple

from detection.risk_scorer import RiskResult, RiskScorer


@dataclass
class DetectionConfig:
    candidate_fields: Tuple[str, ...]   # champs à considérer comme quasi-identifiants potentiels
    prune_threshold: float = 0.15       # seuil minimal pour qu'une combinaison soit étendue
    max_depth: int = 4                  # profondeur maximale (nombre de champs combinés)


class AprioriCombinationDetector:
    """
    Explore les combinaisons de champs par profondeur croissante, en
    n'étendant que les combinaisons déjà jugées "intéressantes" au niveau
    précédent (score >= prune_threshold), jusqu'à max_depth ou jusqu'à ce
    qu'aucune combinaison ne dépasse plus le seuil.
    """

    def __init__(self, scorer: RiskScorer, config: DetectionConfig):
        self.scorer = scorer
        self.config = config

    def detect(self, records: List[dict]) -> List[RiskResult]:
        """
        Retourne la liste des RiskResult pour TOUTES les combinaisons évaluées
        (pas seulement celles qui déclenchent une alerte) -- utile pour
        l'observabilité et le débogage ; filtrer sur .triggered pour ne
        garder que les alertes réelles.
        """
        all_results: List[RiskResult] = []

        # Niveau 1 : chaque champ candidat seul
        current_level: List[Tuple[str, ...]] = [(f,) for f in self.config.candidate_fields]
        survivors: List[Tuple[str, ...]] = []

        for fields in current_level:
            result = self.scorer.score(records, fields)
            all_results.append(result)
            if result.score >= self.config.prune_threshold:
                survivors.append(fields)

        depth = 1
        while survivors and depth < self.config.max_depth:
            depth += 1
            next_candidates = self._extend(survivors, self.config.candidate_fields)
            new_survivors: List[Tuple[str, ...]] = []

            for fields in next_candidates:
                result = self.scorer.score(records, fields)
                all_results.append(result)
                if result.score >= self.config.prune_threshold:
                    new_survivors.append(fields)

            survivors = new_survivors

        return all_results

    @staticmethod
    def _extend(survivors: List[Tuple[str, ...]], all_fields: Tuple[str, ...]) -> List[Tuple[str, ...]]:
        """
        Étend chaque combinaison survivante d'un champ supplémentaire non
        déjà présent, en évitant les doublons (même ensemble de champs
        généré depuis deux parents différents -> on ne le teste qu'une fois).
        """
        seen = set()
        extended = []
        for combo in survivors:
            remaining = [f for f in all_fields if f not in combo]
            for new_field in remaining:
                candidate = tuple(sorted(combo + (new_field,)))
                if candidate not in seen:
                    seen.add(candidate)
                    extended.append(candidate)
        return extended

    def triggered_only(self, records: List[dict]) -> List[RiskResult]:
        """Raccourci : ne retourne que les combinaisons qui déclenchent réellement une alerte."""
        return [r for r in self.detect(records) if r.triggered]