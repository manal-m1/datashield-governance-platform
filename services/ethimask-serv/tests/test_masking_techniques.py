"""
Tests EthiMask - couvre chaque technique de masquage et les types de données sensibles.
Lancer avec : pytest tests/test_masking_techniques.py -v
"""
import pytest
import pytest_asyncio
from backend.masking_techniques import ContextualMasker, MaskingTechnique
from backend.score_calculator import MaskingLevel


@pytest_asyncio.fixture
async def masker():
    """Masker sans DB ni vault — tests unitaires purs, pas de dépendance MongoDB."""
    return ContextualMasker(db=None, vault=None)


class TestPseudonymization:

    @pytest.mark.asyncio
    async def test_name_returns_plausible_fake(self, masker):
        result, tech = await masker.mask("Karim Idrissi", "name", MaskingLevel.PARTIAL, MaskingTechnique.PSEUDONYMIZATION)
        assert tech == "pseudonymization"
        assert result != "Karim Idrissi"
        assert result in ["Mohammed A.", "Fatima B.", "Ahmed C."]

    @pytest.mark.asyncio
    async def test_email_masked_with_domain_format(self, masker):
        result, tech = await masker.mask("karim@test.com", "email", MaskingLevel.PARTIAL, MaskingTechnique.PSEUDONYMIZATION)
        assert tech == "pseudonymization"
        assert "@masked.com" in result

    @pytest.mark.asyncio
    async def test_consistency_same_input_same_output(self, masker):
        r1, _ = await masker.mask("test@x.com", "email", MaskingLevel.PARTIAL, MaskingTechnique.PSEUDONYMIZATION)
        r2, _ = await masker.mask("test@x.com", "email", MaskingLevel.PARTIAL, MaskingTechnique.PSEUDONYMIZATION)
        assert r1 == r2  # cache mémoire garantit la cohérence dans une même session

    @pytest.mark.asyncio
    async def test_unknown_entity_type_uses_generic_pseudo(self, masker):
        result, tech = await masker.mask("some_value", "unknown_type", MaskingLevel.PARTIAL, MaskingTechnique.PSEUDONYMIZATION)
        assert tech == "pseudonymization"
        assert result.startswith("[PSEUDO_")


class TestGeneralization:

    @pytest.mark.asyncio
    async def test_age_generalized_to_range(self, masker):
        result, tech = await masker.mask(35, "age", MaskingLevel.PARTIAL, MaskingTechnique.GENERALIZATION)
        assert tech == "generalization"
        assert result == "30-49"

    @pytest.mark.asyncio
    async def test_salary_generalized_to_bracket(self, masker):
        result, tech = await masker.mask(15000, "salary", MaskingLevel.PARTIAL, MaskingTechnique.GENERALIZATION)
        assert tech == "generalization"
        assert result == "10K-20K MAD"

    @pytest.mark.asyncio
    async def test_unknown_entity_generic_generalization(self, masker):
        result, tech = await masker.mask("value", "city", MaskingLevel.PARTIAL, MaskingTechnique.GENERALIZATION)
        assert tech == "generalization"
        assert result == "[CITY_GEN]"


class TestSuppression:

    @pytest.mark.asyncio
    async def test_suppression_returns_none(self, masker):
        result, tech = await masker.mask("secret_value", "critical_field", MaskingLevel.FULL, MaskingTechnique.SUPPRESSION)
        assert result is None
        assert tech == "suppression"

    @pytest.mark.asyncio
    async def test_none_input_short_circuits(self, masker):
        result, tech = await masker.mask(None, "any_field", MaskingLevel.FULL, MaskingTechnique.SUPPRESSION)
        assert result is None
        assert tech == "none"  # court-circuité avant même d'atteindre la technique

    @pytest.mark.asyncio
    async def test_level_none_bypasses_masking_entirely(self, masker):
        result, tech = await masker.mask("visible_value", "any_field", MaskingLevel.NONE, MaskingTechnique.SUPPRESSION)
        assert result == "visible_value"
        assert tech == "none"


class TestDifferentialPrivacy:

    @pytest.mark.asyncio
    async def test_salary_noise_applied(self, masker):
        original = 15000.0
        result, tech = await masker.mask(original, "salary", MaskingLevel.DIFFERENTIAL_PRIVACY, MaskingTechnique.PERTURBATION)
        assert tech == "differential_privacy_laplace"
        assert isinstance(result, float)
        # Le bruit de Laplace change quasi systématiquement la valeur
        assert result != original

    @pytest.mark.asyncio
    async def test_non_numeric_value_unchanged(self, masker):
        result, tech = await masker.mask("not_a_number", "field", MaskingLevel.DIFFERENTIAL_PRIVACY, MaskingTechnique.PERTURBATION)
        assert result == "not_a_number"
        assert tech == "differential_privacy_laplace"

    @pytest.mark.asyncio
    async def test_noise_magnitude_reasonable(self, masker):
        """Le bruit ne doit pas rendre la valeur absurde (garde-fou qualité)."""
        original = 15000.0
        result, _ = await masker.mask(original, "salary", MaskingLevel.DIFFERENTIAL_PRIVACY, MaskingTechnique.PERTURBATION)
        assert abs(result - original) < 100  # epsilon=1.0, sensitivity=1.0 → bruit typiquement faible


class TestFPE:

    @pytest.mark.asyncio
    async def test_cin_preserves_length_and_alphabet(self, masker):
        original = "AB123456"
        result, tech = await masker.mask(original, "cin", MaskingLevel.ENCRYPTED, MaskingTechnique.FPE)
        assert tech == "format_preserving_encryption"
        assert len(result) == len(original)
        assert result != original
        assert result.isalnum()

    @pytest.mark.asyncio
    async def test_phone_preserves_digit_format(self, masker):
        original = "0612345678"
        result, tech = await masker.mask(original, "phone", MaskingLevel.PARTIAL, MaskingTechnique.FPE)
        assert tech == "format_preserving_encryption"
        assert len(result) == len(original)
        assert result.isdigit()

    @pytest.mark.asyncio
    async def test_account_number_preserves_length(self, masker):
        original = "123456789012"
        result, tech = await masker.mask(original, "account_number", MaskingLevel.PARTIAL, MaskingTechnique.FPE)
        assert len(result) == len(original)
        assert result != original

    @pytest.mark.asyncio
    async def test_fpe_deterministic_same_key(self, masker):
        """Même clé + même entrée = même sortie (contrairement à la pseudonymisation aléatoire)."""
        r1, _ = await masker.mask("AB123456", "cin", MaskingLevel.ENCRYPTED, MaskingTechnique.FPE)
        r2, _ = await masker.mask("AB123456", "cin", MaskingLevel.ENCRYPTED, MaskingTechnique.FPE)
        assert r1 == r2


class TestHomomorphicEncryption:

    @pytest.mark.asyncio
    async def test_numeric_value_encrypted(self, masker):
        result, tech = await masker.mask(15000.0, "salary", MaskingLevel.ENCRYPTED, MaskingTechnique.ENCRYPTION)
        assert tech in ("homomorphic_encryption", "hashing_fallback")
        assert result != "15000.0"
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_string_value_falls_back_to_hashing(self, masker):
        result, tech = await masker.mask("not_numeric", "field", MaskingLevel.ENCRYPTED, MaskingTechnique.ENCRYPTION)
        assert "hash" in tech.lower()
        assert result.startswith("HEX_") or result.startswith("ENC_")


class TestHashing:

    @pytest.mark.asyncio
    async def test_hashing_produces_sha256(self, masker):
        result, tech = await masker.mask("sensitive_value", "field", MaskingLevel.FULL, MaskingTechnique.HASHING)
        assert tech == "hashing"
        assert len(result) == 64  # longueur d'un hash SHA-256 en hex

    @pytest.mark.asyncio
    async def test_hashing_deterministic(self, masker):
        r1, _ = await masker.mask("same_value", "field", MaskingLevel.FULL, MaskingTechnique.HASHING)
        r2, _ = await masker.mask("same_value", "field", MaskingLevel.FULL, MaskingTechnique.HASHING)
        assert r1 == r2


class TestTokenization:

    @pytest.mark.asyncio
    async def test_tokenization_without_vault_returns_error_marker(self, masker):
        """masker créé avec vault=None dans la fixture → doit gérer l'absence proprement."""
        result, tech = await masker.mask("4242424242424242", "card", MaskingLevel.FULL, MaskingTechnique.TOKENIZATION)
        assert tech == "tokenization_error"
        assert result == "[TOKENIZATION_UNAVAILABLE]"

    @pytest.mark.asyncio
    async def test_tokenization_with_mock_vault(self):
        class FakeVault:
            async def tokenize(self, value, entity_type):
                return f"TOK_fake_{entity_type}"

        masker_with_vault = ContextualMasker(db=None, vault=FakeVault())
        result, tech = await masker_with_vault.mask("4242424242424242", "card", MaskingLevel.FULL, MaskingTechnique.TOKENIZATION)
        assert tech == "tokenization"
        assert result == "TOK_fake_card"


class TestPartialMasking:

    @pytest.mark.asyncio
    async def test_email_partial_mask_format(self, masker):
        result = masker._partial_mask("karim@test.com", "email")
        assert result.startswith("ka")
        assert "***@" in result

    @pytest.mark.asyncio
    async def test_generic_partial_mask_keeps_edges(self, masker):
        result = masker._partial_mask("123456789", "generic")
        assert result[:2] == "12"
        assert result[-2:] == "89"
        assert "*" in result

    @pytest.mark.asyncio
    async def test_short_value_fully_masked(self, masker):
        result = masker._partial_mask("abc", "generic")
        assert result == "***"


class TestEnumImplementationConsistency:
    """Empêche toute régression future : chaque technique déclarée dans l'enum
    doit produire le nom de technique attendu, pas tomber dans un fallback silencieux."""

    EXPECTED_TECHNIQUE_NAMES = {
        MaskingTechnique.PSEUDONYMIZATION: "pseudonymization",
        MaskingTechnique.GENERALIZATION: "generalization",
        MaskingTechnique.SUPPRESSION: "suppression",
        MaskingTechnique.PERTURBATION: "differential_privacy_laplace",
        MaskingTechnique.HASHING: "hashing",
        MaskingTechnique.FPE: "format_preserving_encryption",
    }

    TEST_VALUES = {
        MaskingTechnique.PSEUDONYMIZATION: ("Karim", "name"),
        MaskingTechnique.GENERALIZATION: ("35", "age"),
        MaskingTechnique.SUPPRESSION: ("value", "field"),
        MaskingTechnique.PERTURBATION: (1000.0, "salary"),
        MaskingTechnique.HASHING: ("value", "field"),
        MaskingTechnique.FPE: ("AB123456", "cin"),
    }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("technique", list(EXPECTED_TECHNIQUE_NAMES.keys()))
    async def test_technique_matches_expected_name(self, masker, technique):
        value, entity_type = self.TEST_VALUES[technique]
        _, tech_used = await masker.mask(value, entity_type, MaskingLevel.PARTIAL, technique)
        assert tech_used == self.EXPECTED_TECHNIQUE_NAMES[technique]


class TestAuditLogSafety:
    """Vérifie qu'aucune valeur brute ou masquée ne peut se retrouver dans un log d'audit."""

    def test_audit_entry_schema_is_closed(self):
        from main import build_audit_entry, AUDIT_ALLOWED_KEYS
        from backend.score_calculator import MaskingLevel, UserRole

        entry = build_audit_entry(
            field="cin", entity_type="cin", sensitivity="high",
            level=MaskingLevel.ENCRYPTED, technique="format_preserving_encryption",
            role=UserRole.DATA_LABELER
        )
        assert set(entry.keys()) == AUDIT_ALLOWED_KEYS
        assert "value" not in entry
        assert "masked_value" not in entry
        assert "raw_value" not in entry

    def test_audit_entry_rejects_extra_keys(self):
        """Si un jour quelqu'un modifie build_audit_entry pour ajouter une valeur,
        ce test doit échouer et alerter."""
        from main import AUDIT_ALLOWED_KEYS
        forbidden_keys = {"value", "masked_val", "raw_data", "original_value"}
        assert forbidden_keys.isdisjoint(AUDIT_ALLOWED_KEYS)