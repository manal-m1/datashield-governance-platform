from dataclasses import dataclass
from itertools import combinations
from typing import List, Tuple

from detection.risk_scorer import RiskResult
from detection.fuzzy_risk_scorer import FuzzyRiskScorer


@dataclass
class DetectionConfig:
    candidate_fields: Tuple[str, ...]
    max_depth: int = 2


class CombinationDetector:

    def __init__(self, scorer: FuzzyRiskScorer, config: DetectionConfig):
        self.scorer = scorer
        self.config = config

    def detect(self, records: List[dict]) -> List[RiskResult]:
        results = []

        if not records:
            return results

        fields_pool = tuple(dict.fromkeys(self.config.candidate_fields))

        max_depth = min(
            self.config.max_depth,
            len(fields_pool)
        )

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
