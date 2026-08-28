# """
# StreamShield - Definitions partagees pour le scoring de risque

# Ce module ne contient plus de logique de scoring active -- FuzzyRiskScorer
# (detection/fuzzy_risk_scorer.py) est le scorer utilise en production dans
# consumer/main.py.

# Ce fichier garde uniquement les elements PARTAGES entre les scorers
# (structure de resultat, tables de sensibilite), pour que FuzzyRiskScorer
# puisse les importer sans dupliquer ces definitions :

#     RiskResult              -- structure de sortie commune, utilisee dans
#                                 consumer/main.py, api/main.py,
#                                 apriori_detector.py, fuzzy_risk_scorer.py
#     SENSITIVITY_ENCODING     -- table low/medium/high/critical -> [0,1]
#     DEFAULT_FIELD_SENSITIVITY -- sensibilite par defaut, par champ
# """
# from dataclasses import dataclass
# from typing import Dict, Tuple


# # ---------------------------------------------------------------------------
# # Encodage des niveaux de sensibilite
# # ---------------------------------------------------------------------------

# SENSITIVITY_ENCODING: Dict[str, float] = {
#     "low": 0.2,
#     "medium": 0.5,
#     "high": 0.8,
#     "critical": 1.0,
# }


# # ---------------------------------------------------------------------------
# # Sensibilite des champs
# # ---------------------------------------------------------------------------

# # DEFAULT_FIELD_SENSITIVITY: Dict[str, str] = {
# #     # Champs de production - contexte marocain
# #     "ville": "low",
# #     "code_postal": "medium",
# #     "sexe": "low",
# #     "date_naissance": "high",
# #     "cin": "critical",
# #     "email": "high",
# #     "telephone": "high",
# #     "salaire": "high",
# #     "nom": "critical",

# #     # Champs UCI Adult - validation academique
# #     "age": "high",
# #     "sex": "low",
# #     "race": "medium",
# #     "native_country": "medium",
# #     "education": "low",
# #     "workclass": "low",
# #     "marital_status": "medium",
# #     "occupation": "low",
# # }


# # ---------------------------------------------------------------------------
# # Structure de resultat commune
# # ---------------------------------------------------------------------------

# @dataclass
# class RiskResult:
#     """
#     Resultat d'un calcul de risque pour une combinaison de champs.
#     Format de sortie commun a tous les scorers (FuzzyRiskScorer et
#     tout scorer futur) -- consomme par AprioriCombinationDetector,
#     consumer/main.py et api/main.py.
#     """
#     fields: Tuple[str, ...]
#     k: int
#     uniqueness: float
#     avg_sensitivity: float
#     score: float
#     triggered: bool
#     sample_size: int
"""
StreamShield - Definitions partagées pour le scoring de risque.

Ce module contient uniquement les éléments partagés entre les composants
de scoring.

La sensibilité des champs est maintenant stockée dans MongoDB
(collection : streamshield_field_sensitivity).
"""

from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Encodage des niveaux de sensibilité
# ---------------------------------------------------------------------------

SENSITIVITY_ENCODING: Dict[str, float] = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}


# ---------------------------------------------------------------------------
# Structure de résultat commune
# ---------------------------------------------------------------------------

@dataclass
class RiskResult:
    """
    Résultat du calcul de risque pour une combinaison de champs.
    """

    fields: Tuple[str, ...]
    k: int
    uniqueness: float
    avg_sensitivity: float
    score: float
    triggered: bool
    sample_size: int