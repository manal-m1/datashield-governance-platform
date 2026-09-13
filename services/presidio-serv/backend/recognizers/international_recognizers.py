
"""
International PII Recognizers
Supports: Chinese, Japanese, Korean, Russian, Hindi, Hebrew, German, French
"""
import re
from typing import List, Optional
from presidio_analyzer import Pattern, PatternRecognizer
from backend.recognizers.moroccan_base_recognizer import MoroccanPatternRecognizer

class ChineseIDRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("CHINESE_ID_18", r"\b[1-6]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b", 0.85),
        Pattern("CHINESE_ID_15", r"\b[1-6]\d{5}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}\b", 0.7),
    ]
    CONTEXT = ["身份证", "身份", "证号", "chinese national id", "中国身份证"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="CHINESE_ID",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class ChinesePhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("CHINESE_MOBILE", r"\b(?:\+86)1[3-9]\d{9}\b", 0.7),
        Pattern("CHINESE_MOBILE_SPACED", r"\+86[\s-]?1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}\b", 0.65),
    ]
    CONTEXT = ["电话", "手机", "中国手机", "联系电话"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="CHINESE_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class ChineseBankAccountRecognizer(MoroccanPatternRecognizer):
    PATTERNS = [Pattern("CHINESE_BANK_UNIONPAY", r"\b62\d{14,17}\b", 0.5)]
    CONTEXT = ["银行", "账户", "卡号", "中国银行", "银联", "unionpay", "chine", "china"]

    def __init__(self, supported_language="en", supported_entity="CHINESE_BANK_ACCOUNT"):
        super().__init__(
            supported_entity=supported_entity,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
            context_mandatory=True,
        )


class JapaneseMyNumberRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("JAPAN_MY_NUMBER", r"\b\d{12}\b", 0.1),
        Pattern("JAPAN_MY_NUMBER_FORMATTED", r"\b\d{4}-\d{4}-\d{4}\b", 0.6),
    ]
    CONTEXT = ["マイナンバー", "個人番号", "mynumber"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="JAPAN_MY_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class JapanesePhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("JAPAN_PHONE", r"\b\+81\d{9,10}\b", 0.8),
    ]
    CONTEXT = ["電話番号", "携帯電話", "日本の電話"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="JAPAN_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class KoreanRRNRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("KOREAN_RRN", r"\b\d{6}-[1-4]\d{6}\b", 0.8),
    ]
    CONTEXT = ["주민등록번호", "주민번호"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="KOREAN_RRN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class KoreanPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("KOREAN_MOBILE", r"\b\+82[\s-]?1[016789][\s-]?\d{3,4}[\s-]?\d{4}\b", 0.7),
    ]
    CONTEXT = ["전화번호", "휴대폰번호"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="KOREAN_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class RussianPassportRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("RUSSIAN_PASSPORT", r"\b\d{4}\s\d{6}\b", 0.6),
    ]
    CONTEXT = ["паспорт", "серия и номер"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="RUSSIAN_PASSPORT",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class FrenchPassportRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("PASSPORT_FR", r"\b\d{2}[A-Z]{2}\d{5}\b", 0.80),
    ]
    CONTEXT = ["passport", "passeport", "france"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="PASSPORT_FR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class USPassportRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("PASSPORT_US", r"\b\d{9}\b", 0.75),
    ]
    CONTEXT = ["passport", "usa"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="PASSPORT_US",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class RussianPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("RUSSIAN_PHONE", r"\b\+7\d{10}\b", 0.75),
    ]
    CONTEXT = ["телефон", "мобильный телефон"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="RUSSIAN_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class FrenchPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("PHONE_FR", r"\b(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}\b", 0.80),
    ]
    CONTEXT = ["téléphone", "portable", "france"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="PHONE_FR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class USPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("PHONE_US", r"\b(?:\+1)?[2-9]\d{2}[2-9]\d{6}\b", 0.80),
    ]
    CONTEXT = ["phone", "usa", "united states"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="PHONE_US",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class GermanPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("PHONE_DE", r"\b(?:\+49)[1-9]\d{7,13}\b", 0.80),
    ]
    CONTEXT = ["telefon", "deutschland", "germany"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="PHONE_DE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class IndianAadhaarRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("INDIAN_AADHAAR", r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b", 0.6),
    ]
    CONTEXT = ["आधार", "aadhaar number", "aadhar card"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="INDIAN_AADHAAR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class IndianPANRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("INDIAN_PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b", 0.85),
    ]
    CONTEXT = ["permanent account number", "income tax pan"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="INDIAN_PAN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class HebrewIDRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("ISRAELI_ID", r"\b\d{9}\b", 0.1),
    ]
    CONTEXT = ["תעודת זהות", "ת.ז", "israeli id number"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="ISRAELI_ID",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class GermanIDRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("GERMAN_ID", r"\b[CFGHJKLMNPRTVWXYZ0-9]{9}\b", 0.4),
    ]
    CONTEXT = ["personalausweisnummer", "ausweisnummer"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="GERMAN_ID",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class FrenchNIRRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("FRENCH_NIR", r"\b[12]\d{2}(0[1-9]|1[0-2])\d{2}\d{3}\d{3}\d{2}\b", 0.85),
        Pattern("FRENCH_NIR_SPACED", r"\b[12]\s\d{2}\s(0[1-9]|1[0-2])\s\d{2}\s\d{3}\s\d{3}\s\d{2}\b", 0.8),
    ]
    CONTEXT = ["numéro de sécurité sociale", "n° insee", "numéro nir"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="FRENCH_NIR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class FrenchIBANRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("IBAN_FR", r"\bFR\d{25}\b", 0.95),
    ]
    CONTEXT = ["iban", "france", "compte bancaire"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="IBAN_FR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


class GermanIBANRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("IBAN_DE", r"\bDE\d{20}\b", 0.95),
    ]
    CONTEXT = ["iban", "germany", "bankkonto"]

    def __init__(self, supported_language: str = "en"):
        super().__init__(
            supported_entity="IBAN_DE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language,
        )


# Export all recognizers
INTERNATIONAL_RECOGNIZERS = [
    ChineseIDRecognizer,
    ChinesePhoneRecognizer,
    ChineseBankAccountRecognizer,
    JapaneseMyNumberRecognizer,
    JapanesePhoneRecognizer,
    KoreanRRNRecognizer,
    KoreanPhoneRecognizer,
    RussianPassportRecognizer,
    RussianPhoneRecognizer,
    IndianAadhaarRecognizer,
    IndianPANRecognizer,
    HebrewIDRecognizer,
    GermanIDRecognizer,
    FrenchNIRRecognizer,
    FrenchPhoneRecognizer,
    USPhoneRecognizer,
    GermanPhoneRecognizer,
    FrenchIBANRecognizer,
    GermanIBANRecognizer,
    FrenchPassportRecognizer,
    USPassportRecognizer,
]


def register_all_international(registry, languages=None):
    """Register all international recognizers for the given languages"""
    if languages is None:
        languages = ["en", "fr"]

    count = 0
    for lang in languages:
        for RecognizerClass in INTERNATIONAL_RECOGNIZERS:
            try:
                recognizer = RecognizerClass(supported_language=lang)
                registry.add_recognizer(recognizer)
                count += 1
            except Exception as e:
                print(f"⚠️ Failed to register {RecognizerClass.__name__}: {e}")

    print(f"✅ Registered {count} international recognizers")
    return count
