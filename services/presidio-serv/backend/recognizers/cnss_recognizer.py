import re
from typing import List, Optional
from presidio_analyzer import Pattern
from .moroccan_base_recognizer import MoroccanPatternRecognizer


class MoroccanCNSSRecognizer(MoroccanPatternRecognizer):
    """
    CNSS marocain : 9 chiffres (immatriculation employé), parfois 12 pour l'employeur.
    Aucun format n'est distinguable d'un simple entier -> contexte OBLIGATOIRE.
    """
    
    PATTERNS = [
        Pattern("CNSS_SALARIE", r"\b\d{9}\b", 0.5),
        Pattern("CNSS_EMPLOYEUR", r"\b\d{12}\b", 0.5),
    ]
    
    CONTEXT = [
        "cnss", "sécurité sociale", "caisse nationale", 
        "immatriculation cnss", "cotisant", "n° cnss",
        "الضمان الاجتماعي", "الصندوق الوطني"
    ]
    
    def __init__(
        self,
        patterns: Optional[List[Pattern]] = None,
        context: Optional[List[str]] = None,
        supported_language: str = "en",
        supported_entity: str = "CNSS",
    ):
        patterns = patterns if patterns else self.PATTERNS
        context = context if context else self.CONTEXT
        
        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=context,
            supported_language=supported_language,
            context_mandatory=True,   # ✅ pas de détection sans le mot "CNSS" à proximité
        )