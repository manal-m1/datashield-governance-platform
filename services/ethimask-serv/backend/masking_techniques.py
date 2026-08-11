import hashlib
import random
import uuid
import os
from enum import Enum
from typing import Any, Tuple, Optional
import numpy as np
import pyffx
from .score_calculator import MaskingLevel


class MaskingTechnique(str, Enum):
    PSEUDONYMIZATION = "pseudonymization"
    GENERALIZATION = "generalization"
    SUPPRESSION = "suppression"
    PERTURBATION = "perturbation"
    TOKENIZATION = "tokenization"
    HASHING = "hashing"
    ENCRYPTION = "encryption"
    FPE = "fpe"


FPE_KEY_ENV = os.getenv("FPE_KEY")
if not FPE_KEY_ENV:
    raise RuntimeError("FPE_KEY environment variable is required for Format-Preserving Encryption")
FPE_KEY = FPE_KEY_ENV.encode()
FPE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class ContextualMasker:
    def __init__(self, db=None, vault=None, he_context_provider=None):
        """
        db: connexion Mongo, pour persister le cache de pseudonymisation
        vault: instance de TokenVault, requise pour la technique TOKENIZATION
        he_context_provider: callable retournant le PublicContext TenSEAL
                              (ex: he_manager.get_public_context)
        """
        self.db = db
        self.vault = vault
        self.pseudonym_cache = {}  # cache mémoire local (source de vérité = Mongo si db fourni)

        try:
            import tenseal as ts
            if he_context_provider is not None:
                self.ctx = he_context_provider()
            else:
                self.ctx = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
                self.ctx.global_scale = 2**40
                self.ctx.generate_galois_keys()
            self.he_available = True
        except ImportError:
            self.he_available = False
            print("⚠️ TenSEAL not available. HE will fall back to Hashing.")

    async def mask(self, value: Any, entity_type: str, level: MaskingLevel, technique: Optional[MaskingTechnique] = None) -> Tuple[Any, str]:
        if value is None or level == MaskingLevel.NONE:
            return value, "none"
        str_value = str(value)

        if technique is None:
            if level == MaskingLevel.ENCRYPTED: technique = MaskingTechnique.ENCRYPTION
            elif level == MaskingLevel.FULL: technique = MaskingTechnique.SUPPRESSION
            elif level == MaskingLevel.PARTIAL: technique = MaskingTechnique.GENERALIZATION
            elif level == MaskingLevel.DIFFERENTIAL_PRIVACY: technique = MaskingTechnique.PERTURBATION
            else: technique = MaskingTechnique.PSEUDONYMIZATION

        technique_str = technique.value if isinstance(technique, MaskingTechnique) else str(technique)

        if technique_str == MaskingTechnique.ENCRYPTION.value:
            return self._encrypt_he(value, str_value)

        elif technique_str == MaskingTechnique.FPE.value:
            return self._fpe(str_value, entity_type)

        elif technique_str == MaskingTechnique.PERTURBATION.value:
            return self._apply_laplace_mechanism(value), "differential_privacy_laplace"

        elif technique_str == MaskingTechnique.PSEUDONYMIZATION.value:
            result = await self._pseudonymize(str_value, entity_type)
            return result, "pseudonymization"

        elif technique_str == MaskingTechnique.GENERALIZATION.value:
            return self._generalize(str_value, entity_type), "generalization"

        elif technique_str == MaskingTechnique.SUPPRESSION.value:
            return None, "suppression"

        elif technique_str == MaskingTechnique.HASHING.value:
            return hashlib.sha256(str_value.encode()).hexdigest(), "hashing"

        elif technique_str == MaskingTechnique.TOKENIZATION.value:
            if self.vault is None:
                return "[TOKENIZATION_UNAVAILABLE]", "tokenization_error"
            token = await self.vault.tokenize(str_value, entity_type)
            return token, "tokenization"

        return self._partial_mask(str_value, entity_type), "partial_masking"

    # ----------------------------------------------------------------

    def _encrypt_he(self, value: Any, str_value: str) -> Tuple[str, str]:
        if not self.he_available:
            return f"ENC_{hashlib.sha256(str_value.encode()).hexdigest()}", "hashing_fallback"
        try:
            val = float(value)
            import tenseal as ts
            enc_vec = ts.ckks_vector(self.ctx, [val])
            return enc_vec.serialize().hex(), "homomorphic_encryption"
        except ValueError:
            return f"HEX_{hashlib.sha256(str_value.encode()).hexdigest()}", "hashing_fallback"

    def _fpe(self, value: str, entity_type: str) -> Tuple[str, str]:
        try:
            if value.isdigit():
                cipher = pyffx.Integer(FPE_KEY, length=len(value))
                return str(cipher.encrypt(int(value))).zfill(len(value)), "format_preserving_encryption"
            cipher = pyffx.String(FPE_KEY, alphabet=FPE_ALPHABET, length=len(value))
            return cipher.encrypt(value.upper()), "format_preserving_encryption"
        except Exception:
            return self._partial_mask(value, entity_type), "fpe_fallback_partial"

    def _apply_laplace_mechanism(self, value: Any, epsilon: float = 1.0, sensitivity: float = 1.0) -> Any:
        try:
            val = float(value)
            scale = sensitivity / epsilon
            noise = np.random.laplace(0, scale)
            return round(val + noise, 2)
        except (ValueError, TypeError):
            return value

    async def _pseudonymize(self, value: str, entity_type: str) -> str:
        key = f"{entity_type}:{value}"

        if key in self.pseudonym_cache:
            return self.pseudonym_cache[key]

        if self.db is not None:
            cached = await self.db.pseudonym_cache.find_one({"_id": key})
            if cached:
                self.pseudonym_cache[key] = cached["result"]
                return cached["result"]

        if entity_type == "name":
            result = random.choice(["Mohammed A.", "Fatima B.", "Ahmed C."])
        elif entity_type == "email":
            result = f"user_{random.randint(1000,9999)}@masked.com"
        else:
            result = f"[PSEUDO_{uuid.uuid4().hex[:6]}]"

        self.pseudonym_cache[key] = result
        if self.db is not None:
            await self.db.pseudonym_cache.update_one(
                {"_id": key}, {"$set": {"result": result, "entity_type": entity_type}}, upsert=True
            )
        return result

    def _generalize(self, value: str, entity_type: str) -> str:
        if entity_type == "age": return "30-49"
        if entity_type == "salary": return "10K-20K MAD"
        return f"[{entity_type.upper()}_GEN]"

    def _partial_mask(self, value: str, entity_type: str) -> str:
        if entity_type == "email":
            parts = value.split("@")
            return (parts[0][:2] + "***@" + parts[1]) if len(parts) == 2 else value
        return value[:2] + "*" * (max(0, len(value)-4)) + value[-2:] if len(value) > 4 else "*"*len(value)