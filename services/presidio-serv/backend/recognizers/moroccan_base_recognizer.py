"""
Moroccan Base Recognizer for Microsoft Presidio
Implements Algorithm 3 (Weighted Scoring) as specified in Cahier des Charges Section 5.5
"""
import re
from typing import List, Optional, Callable
from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

class MoroccanPatternRecognizer(PatternRecognizer):
    """
    Base class for Moroccan PII recognizers.
    score_final = 0.5 * score_pattern + 0.3 * score_context + 0.2 * score_validation
    """

    MOROCCAN_GEO_KEYWORDS = [
        "maroc", "morocco", "+212", "casablanca", "rabat", "salé", "fes", "fès",
        "marrakech", "tanger", "agadir", "kenitra", "meknes", "oujda", "tetouan"
    ]

    def __init__(
        self,
        supported_entity: str,
        patterns: List[Pattern],
        context: Optional[List[str]] = None,
        supported_language: str = "en",
        validator: Optional[Callable[[str], bool]] = None,
        context_mandatory: bool = False,
        require_geo_context: bool = False,   # ✅ AJOUTÉ — c'est ce qui manquait
    ):
        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=None,
            supported_language=supported_language,
        )
        self.supported_entity = supported_entity
        self.manual_context = context
        self.validator = validator
        self.supported_language = supported_language
        self.context_mandatory = context_mandatory
        self.require_geo_context = require_geo_context   # ✅ AJOUTÉ

    def _has_moroccan_geo_context(self, full_text: str) -> bool:
        text_lower = full_text.lower()
        return any(kw in text_lower for kw in self.MOROCCAN_GEO_KEYWORDS)  # ✅ self. ajouté

    def analyze(self, text: str, entities: List[str], nlp_artifacts=None) -> List[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)

        if not results or (entities is not None and self.supported_entity not in entities):
            return results

        # ✅ calculé une seule fois pour tout le texte, pas à chaque résultat
        geo_ok = self._has_moroccan_geo_context(text) if self.require_geo_context else True

        final_results = []

        for result in results:
            if self.require_geo_context and not geo_ok:
                continue

            score_pattern = result.score
            has_context = self._check_context_proximity(text, result.start, result.end, nlp_artifacts)
            score_context = 1.0 if has_context else 0.0

            if self.context_mandatory and not has_context:
                continue

            score_validation = 1.0
            if self.validator:
                match_text = text[result.start:result.end]
                score_validation = 1.0 if self.validator(match_text) else 0.0

            score_final = (0.5 * score_pattern) + (0.3 * score_context) + (0.2 * score_validation)
            result.score = round(score_final, 3)
            final_results.append(result)

        return final_results

    def _check_context_proximity(self, text: str, start: int, end: int, nlp_artifacts=None) -> bool:
        if not self.manual_context:
            return False
        window_size = 40
        context_window = text[max(0, start - window_size):min(len(text), end + window_size)].lower()
        for word in self.manual_context:
            if word.lower() in context_window:
                return True
        return False
# """
# Moroccan Base Recognizer for Microsoft Presidio
# Implements Algorithm 3 (Weighted Scoring) as specified in Cahier des Charges Section 5.5
# """
# import re
# from typing import List, Optional, Callable
# from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

# class MoroccanPatternRecognizer(PatternRecognizer):
#     """
#     Base class for Moroccan PII recognizers.
#     score_final = 0.5 * score_pattern + 0.3 * score_context + 0.2 * score_validation
#     """
    
#     def __init__(
#         self,
#         supported_entity: str,
#         patterns: List[Pattern],
#         context: Optional[List[str]] = None,
#         supported_language: str = "en",
#         validator: Optional[Callable[[str], bool]] = None,
#         context_mandatory: bool = False,   # ✅ NOUVEAU
#     ):
#         super().__init__(
#             supported_entity=supported_entity,
#             patterns=patterns,
#             context=None,
#             supported_language=supported_language,
#         )
#         self.supported_entity = supported_entity
#         self.manual_context = context
#         self.validator = validator
#         self.supported_language = supported_language
#         self.context_mandatory = context_mandatory  # ✅ NOUVEAU
#     MOROCCAN_GEO_KEYWORDS = [
#     "maroc", "morocco", "+212", "casablanca", "rabat", "salé", "fes", "fès",
#     "marrakech", "tanger", "agadir", "kenitra", "meknes", "oujda", "tetouan"]

#     def _has_moroccan_geo_context(self, full_text: str) -> bool:
#         text_lower = full_text.lower()
#         return any(kw in text_lower for kw in MOROCCAN_GEO_KEYWORDS)    

#     def analyze(self, text: str, entities: List[str], nlp_artifacts=None) -> List[RecognizerResult]:
#         results = super().analyze(text, entities, nlp_artifacts)
        
#         if not results or (entities is not None and self.supported_entity not in entities):
#             return results

#         final_results = []
        
#         for result in results:
#             if self.require_geo_context and not self._has_moroccan_geo_context(text):
#                 continue
#             score_pattern = result.score
#             has_context = self._check_context_proximity(text, result.start, result.end, nlp_artifacts)
#             score_context = 1.0 if has_context else 0.0
            
#             # ✅ GATE OBLIGATOIRE : si le contexte est requis et absent, on rejette totalement
#             if self.context_mandatory and not has_context:
#                 continue
            
#             score_validation = 1.0
#             if self.validator:
#                 match_text = text[result.start:result.end]
#                 score_validation = 1.0 if self.validator(match_text) else 0.0
            
#             score_final = (0.5 * score_pattern) + (0.3 * score_context) + (0.2 * score_validation)
#             result.score = round(score_final, 3)
#             final_results.append(result)
            
#         return final_results

#     def _check_context_proximity(self, text: str, start: int, end: int, nlp_artifacts=None) -> bool:
#         if not self.manual_context:
#             return False
#         window_size = 40   # ← 15 est trop court une fois les noms de colonnes ajoutés
#         context_window = text[max(0, start - window_size):min(len(text), end + window_size)].lower()
#         for word in self.manual_context:
#             if word.lower() in context_window:
#                 return True
#         return False