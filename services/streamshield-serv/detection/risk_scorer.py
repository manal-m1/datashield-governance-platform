"""
StreamShield - Tâche 2, étape 3
Formule de score pondéré (section 4.3 du cahier des charges) :

    Score(C) = w1 * (1/k(C)) + w2 * Unicité(C) + w3 * Sensibilité_moyenne(C)

Combine ce que l'étape 2 (CombinationAnalyzer) calcule sur les données réelles
avec une classification de sensibilité par champ. En attendant l'intégration
Apache Atlas (prévue en section 2.5), la classification est fournie ici via
une table configurable -- remplaçable plus tard par un appel Atlas sans
changer la formule elle-même.
"""
from dataclasses import dataclass, field as dc_field
from typing import Dict, Tuple

from detection.frequency_counter import CombinationAnalyzer

# Classification de sensibilité par champ -- même échelle que celle déjà
# utilisée côté EthiMask (low/medium/high/critical), pour rester cohérent
# dans tout le Projet Fédérateur.
SENSITIVITY_ENCODING: Dict[str, float] = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}

DEFAULT_FIELD_SENSITIVITY: Dict[str, str] = {
    "ville": "low",
    "code_postal": "medium",
    "sexe": "low",
    "date_naissance": "high",
    "cin": "critical",
    "email": "high",
    "telephone": "high",
    "salaire": "high",
    "nom": "critical",
}


@dataclass
class RiskWeights:
    """w1 + w2 + w3 n'ont pas d'obligation de sommer à 1, mais c'est plus
    lisible ainsi pour interpréter le score final entre 0 et 1."""
    w1: float = 0.5   # poids de 1/k(C) -- le signal principal (k-anonymat)
    w2: float = 0.3   # poids de Unicité(C)
    w3: float = 0.2   # poids de Sensibilité_moyenne(C)


@dataclass
class RiskResult:
    fields: Tuple[str, ...]
    k: int
    uniqueness: float
    avg_sensitivity: float
    score: float
    triggered: bool
    sample_size: int


class RiskScorer:

    def __init__(
        self,
        weights: RiskWeights = None,
        threshold: float = 0.5,
        field_sensitivity: Dict[str, str] = None,
    ):
        self.weights = weights or RiskWeights()
        self.threshold = threshold
        self.field_sensitivity = field_sensitivity or DEFAULT_FIELD_SENSITIVITY

    def _average_sensitivity(self, fields: Tuple[str, ...]) -> float:
        levels = [self.field_sensitivity.get(f, "medium") for f in fields]
        scores = [SENSITIVITY_ENCODING.get(lvl, 0.5) for lvl in levels]
        return sum(scores) / len(scores) if scores else 0.0

    def score(self, records: list, fields: Tuple[str, ...]) -> RiskResult:
        analysis = CombinationAnalyzer.analyze(records, fields)
        k = analysis["k"]
        uniqueness = analysis["uniqueness"]
        sample_size = analysis["sample_size"]

        if k == 0:
            # Pas assez de données complètes pour cette combinaison dans la
            # fenêtre -- score nul plutôt qu'une division par zéro, et pas
            # déclenché (on ne peut rien affirmer sur une combinaison absente).
            return RiskResult(
                fields=fields, k=0, uniqueness=0.0, avg_sensitivity=0.0,
                score=0.0, triggered=False, sample_size=sample_size,
            )

        avg_sensitivity = self._average_sensitivity(fields)
        risk = 1.0 / k
        raw_score = (
            self.weights.w1 * risk
            + self.weights.w2 * uniqueness
            + self.weights.w3 * avg_sensitivity
        )
        # Borne le score à [0, 1] même si les poids ne somment pas exactement à 1
        clamped_score = max(0.0, min(1.0, raw_score))

        return RiskResult(
            fields=fields,
            k=k,
            uniqueness=uniqueness,
            avg_sensitivity=avg_sensitivity,
            score=clamped_score,
            triggered=clamped_score >= self.threshold,
            sample_size=sample_size,
        )