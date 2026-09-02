
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