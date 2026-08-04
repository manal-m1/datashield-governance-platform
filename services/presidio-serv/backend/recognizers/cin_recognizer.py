import re
from typing import List, Optional
from presidio_analyzer import Pattern
from backend.recognizers.moroccan_base_recognizer import MoroccanPatternRecognizer


class MoroccanCINRecognizer(MoroccanPatternRecognizer):
    """
    CIN marocain officiel : 1-2 lettres (code préfecture) + exactement 6 chiffres.
    Ex: A123456, BE123456
    """
    
    PATTERNS = [
        Pattern("CIN_MAROC_SPACED", r"\b[A-Z]{1,2}\s?\d{3}\s?\d{3}\b", 0.45),
        Pattern("CIN_MAROC_FULL", r"\b[A-Z]{1,2}\d{6}\b", 0.45),  # ✅ exactement 6, plus 6-8
    ]

    CONTEXT = [
    "cin", "carte d'identité", "carte nationale", "n° cin",
    "nationalid", "national id",   # ← AJOUTER : c'est le vrai nom de colonne CSV
    "بطاقة التعريف الوطنية", "البطاقة الوطنية"
]
    
    def __init__(
        self,
        patterns: Optional[List[Pattern]] = None,
        context: Optional[List[str]] = None,
        supported_language: str = "en",
        supported_entity: str = "CIN_MAROC",
    ):
        patterns = patterns if patterns else self.PATTERNS
        context = context if context else self.CONTEXT
        
        def cin_validator(text: str) -> bool:
            clean_text = re.sub(r"\s+", "", text).upper()
            digits_only = re.sub(r"[A-Z]", "", clean_text)
            letters_only = re.sub(r"[0-9]", "", clean_text)
            return 5 <= len(digits_only) <= 6 and 1 <= len(letters_only) <= 2

        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=context,
            supported_language=supported_language,
            validator=cin_validator,
            context_mandatory=True,
            require_geo_context=True   # ← AJOUTER : c'est celui qui manquait, cause des faux positifs BE/AA/AB
)