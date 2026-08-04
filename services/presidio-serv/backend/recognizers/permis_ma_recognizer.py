import re
from typing import List, Optional
from presidio_analyzer import Pattern
from .moroccan_base_recognizer import MoroccanPatternRecognizer


class MoroccanPermisRecognizer(MoroccanPatternRecognizer):
    """
    Permis de conduire marocain : numéro purement numérique, 8 à 10 chiffres.
    Pas de standard public identifiable par regex seul -> contexte OBLIGATOIRE.
    """
    
    PATTERNS = [
        Pattern("PERMIS_MA", r"\b\d{8,10}\b", 0.5),
    ]
    
    CONTEXT = ["permis de conduire", "permis", "driving licence", "driving license",
           "n° permis", "conduite", "رخصة القيادة", "رخصة السياقة"]
    
    def __init__(
        self,
        patterns: Optional[List[Pattern]] = None,
        context: Optional[List[str]] = None,
        supported_language: str = "en",
        supported_entity: str = "PERMIS_MA",
    ):
        patterns = patterns if patterns else self.PATTERNS
        context = context if context else self.CONTEXT
        
        def permis_validator(text: str) -> bool:
            clean = text.strip()
            return clean.isdigit() and 8 <= len(clean) <= 10

        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=context,
            supported_language=supported_language,
            validator=permis_validator,
            context_mandatory=True,   # ✅ élimine "Over18", "brown96", "thomas51"...
        )