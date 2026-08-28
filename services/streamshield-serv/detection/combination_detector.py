# """
# StreamShield - Tâche 2, étape 4 (v2 - corrigée après revue)

# CHANGEMENT v2 : l'élagage "type Apriori" (n'étendre que les combinaisons
# qui dépassent déjà prune_threshold au niveau précédent) a été retiré.

# Justification : cet élagage s'appuie sur la propriété d'anti-monotonie du
# SUPPORT (si un sous-ensemble n'est pas fréquent, le sur-ensemble ne l'est
# pas non plus) -- valide pour l'algorithme Apriori classique (itemsets
# fréquents), mais INVALIDE ici. Pour le k-anonymat, la monotonie va dans
# l'autre sens : ajouter un champ ne peut que réduire ou maintenir k(C),
# donc le risque ne peut que croître ou rester stable. Un champ seul, quasi
# toujours peu risqué (grand k), pouvait donc bloquer l'exploration de toute
# combinaison qui l'inclut -- exactement le cas d'usage central de la
# détection de quasi-identifiants (Sweeney 2000, ville+sexe+date_naissance).

# Avec 4 à ~8 champs candidats, l'espace de combinaisons (2^n - 1, soit 15 à
# 255) reste trivialement énumérable en entier à chaque détection -- pas
# besoin d'élagage pour la performance à cette échelle. Le paramètre
# prune_threshold est conservé dans DetectionConfig pour compatibilité,
# mais n'est plus utilisé pour couper l'exploration.
# """
# from dataclasses import dataclass
# from itertools import combinations
# from typing import List, Tuple

# from detection.risk_scorer import RiskResult
# from detection.fuzzy_risk_scorer import FuzzyRiskScorer

# @dataclass
# class DetectionConfig:
#     candidate_fields: Tuple[str, ...]
#     prune_threshold: float = 0.15   # conservé pour compat, non utilisé pour élaguer (v2)
#     max_depth: int = 4


# class AprioriCombinationDetector:
#     """
#     v2 : énumère EXHAUSTIVEMENT toutes les combinaisons de candidate_fields
#     jusqu'à max_depth, sans élagage sur le score.
#     """

#     def __init__(self, scorer: FuzzyRiskScorer, config: DetectionConfig):
#         self.scorer = scorer
#         self.config = config

#     def detect(self, records: List[dict]) -> List[RiskResult]:
#         all_results: List[RiskResult] = []
#         fields_pool = self.config.candidate_fields
#         max_depth = min(self.config.max_depth, len(fields_pool))

#         for depth in range(1, max_depth + 1):
#             for combo in combinations(fields_pool, depth):
#                 result = self.scorer.score(records, combo)
#                 all_results.append(result)

#         return all_results

#     def triggered_only(self, records: List[dict]) -> List[RiskResult]:
#         return [r for r in self.detect(records) if r.triggered]

#     # NOTE pour une future montée en échelle (>10 champs candidats) :
#     # un élagage sûr pour le k-anonymat ne doit JAMAIS couper sur un score
#     # bas d'un sous-ensemble. Il peut en revanche éviter de re-scorer une
#     # extension d'une combinaison déjà "triggered" == True au niveau
#     # précédent SI ET SEULEMENT SI l'objectif est de ne remonter que la
#     # combinaison minimale suffisante (le plus petit sur-ensemble à risque),
#     # ce qui est une optimisation différente de l'élagage par score bas
#     # actuellement retiré.
from dataclasses import dataclass
from itertools import combinations
from typing import List, Tuple

from detection.risk_scorer import RiskResult
from detection.fuzzy_risk_scorer import FuzzyRiskScorer


@dataclass
class DetectionConfig:
    candidate_fields: Tuple[str, ...]
    max_depth: int = 4


class CombinationDetector:

    def __init__(self, scorer: FuzzyRiskScorer, config: DetectionConfig):
        self.scorer = scorer
        self.config = config

    def detect(self, records: List[dict]) -> List[RiskResult]:
        results = []

        fields_pool = self.config.candidate_fields
        max_depth = min(self.config.max_depth, len(fields_pool))

        for depth in range(1, max_depth + 1):
            for combo in combinations(fields_pool, depth):
                result = self.scorer.score(records, combo)
                results.append(result)

        return results

    def triggered_only(self, records: List[dict]) -> List[RiskResult]:
        return [
            result
            for result in self.detect(records)
            if result.triggered
        ]