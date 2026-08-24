# """
# StreamShield - Tâche 2, étape 3 (v3 - corrigée après revue)

# Formule du score pondéré (section 4.3 du cahier des charges) :

#     Score(C) = w1 * (1/k(C))
#              + w2 * Unicité(C)
#              + w3 * Sensibilité_moyenne(C)

# Composantes :
#     - 1/k(C)              : risque lié au k-anonymat
#     - Unicité(C)          : proportion de classes d'équivalence singleton
#     - Sensibilité_moyenne : sensibilité moyenne des champs de la combinaison

# Corrections :
#   - Unicité(C) utilise désormais la proportion de GROUPES uniques
#     (classes d'équivalence singleton) et non la proportion d'enregistrements
#     uniques. Cette mesure ne se dilue donc plus avec la taille de la fenêtre.
#   - Les sensibilités couvrent les noms de champs utilisés en production
#     ainsi que les noms de champs du jeu UCI Adult utilisé pour la validation.
#   - k=0 est distingué de k=1 :
#       * k=0 : aucun enregistrement exploitable -> score nul
#       * k=1 : combinaison réellement unique -> risque maximal
#   - Le score final est borné dans [0, 1].
#   - Le seuil reste fixé à 0.5. Sa recalibration doit être effectuée après
#     validation de la formule et non utilisée pour masquer un problème
#     dans le calcul du score.
# """

# from dataclasses import dataclass
# from typing import Dict, Tuple, List, Optional

# from detection.frequency_counter import CombinationAnalyzer
# # ---------------------------------------------------------------------------
# # Encodage des niveaux de sensibilité
# # ---------------------------------------------------------------------------
# SENSITIVITY_ENCODING: Dict[str, float] = {
#     "low": 0.2,
#     "medium": 0.5,
#     "high": 0.8,
#     "critical": 1.0,
# }
# # ---------------------------------------------------------------------------
# # Sensibilité des champs
# # ---------------------------------------------------------------------------

# DEFAULT_FIELD_SENSITIVITY: Dict[str, str] = {
#     # Champs de production - contexte marocain
#     "ville": "low",
#     "code_postal": "medium",
#     "sexe": "low",
#     "date_naissance": "high",
#     "cin": "critical",
#     "email": "high",
#     "telephone": "high",
#     "salaire": "high",
#     "nom": "critical",

#     # Champs UCI Adult - validation académique
#     "age": "high",
#     "sex": "low",
#     "race": "medium",
#     "native_country": "medium",
#     "education": "low",
#     "workclass": "low",
#     "marital_status": "medium",
#     "occupation": "low",
# }


# # ---------------------------------------------------------------------------
# # Poids du score
# # ---------------------------------------------------------------------------

# @dataclass(frozen=True)
# class RiskWeights:
#     """
#     Poids des trois composantes du score.

#     Par défaut :
#         w1 = 0.5 -> k-anonymat
#         w2 = 0.3 -> unicité
#         w3 = 0.2 -> sensibilité

#     La somme des poids doit être égale à 1.
#     """

#     w1: float = 0.5
#     w2: float = 0.3
#     w3: float = 0.2

#     def __post_init__(self) -> None:
#         total = self.w1 + self.w2 + self.w3

#         if abs(total - 1.0) > 1e-9:
#             raise ValueError(
#                 f"La somme des poids doit être égale à 1. "
#                 f"Valeur obtenue : {total:.4f}"
#             )

#         if any(weight < 0 for weight in (self.w1, self.w2, self.w3)):
#             raise ValueError(
#                 "Les poids du score doivent être positifs ou nuls."
#             )


# # ---------------------------------------------------------------------------
# # Résultat du calcul de risque
# # ---------------------------------------------------------------------------

# @dataclass
# class RiskResult:
#     fields: Tuple[str, ...]
#     k: int
#     uniqueness: float
#     avg_sensitivity: float
#     score: float
#     triggered: bool
#     sample_size: int


# # ---------------------------------------------------------------------------
# # Calculateur de risque
# # ---------------------------------------------------------------------------

# class RiskScorer:

#     # v3 (suite revue) : en dessous de ce seuil, k(C) et Unicité(C) ne sont
#     # pas statistiquement significatifs -- un échantillon de 1 ou 2
#     # enregistrements donne trivialement k=1 et Unicité=1.0, ce qui produit
#     # un score élevé sans aucun signal de risque réel. Observé concrètement
#     # avec le déclenchement mixte (detection_max_interval_seconds) qui peut
#     # lancer une détection avant qu'assez de messages soient accumulés.
#     MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE = 20

#     def __init__(
#         self,
#         weights: Optional[RiskWeights] = None,
#         threshold: float = 0.5,
#         field_sensitivity: Optional[Dict[str, str]] = None,
#         min_sample_size: Optional[int] = None,
#     ):
#         if not 0.0 <= threshold <= 1.0:
#             raise ValueError(
#                 f"Le seuil doit être compris entre 0 et 1. "
#                 f"Valeur reçue : {threshold}"
#             )

#         self.weights = weights if weights is not None else RiskWeights()
#         self.threshold = threshold
#         self.min_sample_size = (
#             min_sample_size
#             if min_sample_size is not None
#             else self.MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE
#         )

#         self.field_sensitivity = (
#             field_sensitivity
#             if field_sensitivity is not None
#             else DEFAULT_FIELD_SENSITIVITY.copy()
#         )

#     def _average_sensitivity(self, fields: Tuple[str, ...]) -> float:
#         if not fields:
#             return 0.0
#         sensitivity_values = []
#         for field in fields:
#             level = self.field_sensitivity.get(field, "medium")
#             value = SENSITIVITY_ENCODING.get(level, 0.5)
#             sensitivity_values.append(value)
#         return sum(sensitivity_values) / len(sensitivity_values)

#     def score(self, records: List[dict], fields: Tuple[str, ...]) -> RiskResult:
#         if not fields:
#             return RiskResult(
#                 fields=fields, k=0, uniqueness=0.0, avg_sensitivity=0.0,
#                 score=0.0, triggered=False, sample_size=0,
#             )

#         analysis = CombinationAnalyzer.analyze(records, fields)
#         k = analysis["k"]
#         uniqueness = analysis["uniqueness"]
#         sample_size = analysis["sample_size"]

#         # Aucun enregistrement complet disponible
#         if k == 0:
#             return RiskResult(
#                 fields=fields, k=0, uniqueness=0.0, avg_sensitivity=0.0,
#                 score=0.0, triggered=False, sample_size=sample_size,
#             )

#         # v3 (suite revue) : échantillon trop petit pour un calcul fiable --
#         # on retourne k et sample_size réels (utile pour le debug/observabilité)
#         # mais le score est nul et non déclenché, pour ne pas produire une
#         # fausse alerte basée sur un artefact de sous-échantillonnage.
#         if sample_size < self.min_sample_size:
#             return RiskResult(
#                 fields=fields, k=k, uniqueness=0.0, avg_sensitivity=0.0,
#                 score=0.0, triggered=False, sample_size=sample_size,
#             )

#         risk = 1.0 / k
#         avg_sensitivity = self._average_sensitivity(fields)

#         raw_score = (
#             self.weights.w1 * risk
#             + self.weights.w2 * uniqueness
#             + self.weights.w3 * avg_sensitivity
#         )
#         score = max(0.0, min(1.0, raw_score))
#         triggered = score >= self.threshold

#         return RiskResult(
#             fields=fields, k=k, uniqueness=uniqueness,
#             avg_sensitivity=avg_sensitivity, score=score,
#             triggered=triggered, sample_size=sample_size,
#         )
"""
StreamShield - Definitions partagees pour le scoring de risque

Ce module ne contient plus de logique de scoring active -- FuzzyRiskScorer
(detection/fuzzy_risk_scorer.py) est le scorer utilise en production dans
consumer/main.py.

Ce fichier garde uniquement les elements PARTAGES entre les scorers
(structure de resultat, tables de sensibilite), pour que FuzzyRiskScorer
puisse les importer sans dupliquer ces definitions :

    RiskResult              -- structure de sortie commune, utilisee dans
                                consumer/main.py, api/main.py,
                                apriori_detector.py, fuzzy_risk_scorer.py
    SENSITIVITY_ENCODING     -- table low/medium/high/critical -> [0,1]
    DEFAULT_FIELD_SENSITIVITY -- sensibilite par defaut, par champ
"""
from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Encodage des niveaux de sensibilite
# ---------------------------------------------------------------------------

SENSITIVITY_ENCODING: Dict[str, float] = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}


# ---------------------------------------------------------------------------
# Sensibilite des champs
# ---------------------------------------------------------------------------

DEFAULT_FIELD_SENSITIVITY: Dict[str, str] = {
    # Champs de production - contexte marocain
    "ville": "low",
    "code_postal": "medium",
    "sexe": "low",
    "date_naissance": "high",
    "cin": "critical",
    "email": "high",
    "telephone": "high",
    "salaire": "high",
    "nom": "critical",

    # Champs UCI Adult - validation academique
    "age": "high",
    "sex": "low",
    "race": "medium",
    "native_country": "medium",
    "education": "low",
    "workclass": "low",
    "marital_status": "medium",
    "occupation": "low",
}


# ---------------------------------------------------------------------------
# Structure de resultat commune
# ---------------------------------------------------------------------------

@dataclass
class RiskResult:
    """
    Resultat d'un calcul de risque pour une combinaison de champs.
    Format de sortie commun a tous les scorers (FuzzyRiskScorer et
    tout scorer futur) -- consomme par AprioriCombinationDetector,
    consumer/main.py et api/main.py.
    """
    fields: Tuple[str, ...]
    k: int
    uniqueness: float
    avg_sensitivity: float
    score: float
    triggered: bool
    sample_size: int