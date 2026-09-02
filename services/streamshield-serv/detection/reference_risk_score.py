"""
StreamShield - Reference Risk Score

Mesure de référence indépendante de k.

Le score de référence utilise uniquement :
    - l'unicité empirique de la combinaison
    - la sensibilité moyenne des champs

k n'intervient jamais directement dans ce calcul.
"""

from typing import Dict, Tuple, List

from detection.frequency_counter import CombinationAnalyzer
from detection.risk_scorer import SENSITIVITY_ENCODING
from detection.field_sensitivity_repository import DEFAULT_SENSITIVITY

import logging

logger = logging.getLogger(
    "streamshield.reference_risk_scorer"
)
class ReferenceRiskScorer:

    # Poids de la référence
    UNIQUENESS_WEIGHT = 0.7
    SENSITIVITY_WEIGHT = 0.3

    def __init__(self, field_sensitivity: Dict[str, str] = None):
        self.field_sensitivity = field_sensitivity or {}

    def _average_sensitivity(
        self,
        fields: Tuple[str, ...],
    ) -> float:

        if not fields:
            return 0.0

        values = []

        for field in fields:

            level = self.field_sensitivity.get(
                field,
                DEFAULT_SENSITIVITY,
            )

            if level not in SENSITIVITY_ENCODING:
                level = DEFAULT_SENSITIVITY

            values.append(
                SENSITIVITY_ENCODING[level]
            )

        return sum(values) / len(values)

    def score(
        self,
        records: List[dict],
        fields: Tuple[str, ...],
    ) -> float:

        if not fields:
            return 0.0

        analysis = CombinationAnalyzer.analyze(
            records,
            fields,
        )

        sample_size = analysis["sample_size"]

        if sample_size == 0:
            return 0.0

        uniqueness = analysis["uniqueness"]

        sensitivity = self._average_sensitivity(
            fields
        )

        reference_score = (
            self.UNIQUENESS_WEIGHT * uniqueness
            + self.SENSITIVITY_WEIGHT * sensitivity
        )
        logger.info(
            f"REFERENCE SCORE | "
            f"fields={fields} | "
            f"uniqueness={uniqueness:.4f} | "
            f"sensitivity={sensitivity:.4f} | "
            f"reference_score={reference_score:.4f}"
        )

        return max(
            0.0,
            min(1.0, reference_score),
        )