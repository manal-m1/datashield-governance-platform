"""
HE Key Manager - Séparation PublicContext / SecretContext (TenSEAL)
Le SecretContext (clé de déchiffrement) ne quitte jamais ce process.
Seul le PublicContext (chiffrement/calcul) est distribuable aux autres services.
"""
import tenseal as ts


class HEAccessDenied(Exception):
    pass


class HEKeyManager:
    ALLOWED_DECRYPT_ROLES = {"admin", "steward"}

    def __init__(self):
        self._secret_ctx = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=8192,
            coeff_mod_bit_sizes=[60, 40, 40, 60]
        )
        self._secret_ctx.global_scale = 2**40
        self._secret_ctx.generate_galois_keys()

        self._public_ctx = self._secret_ctx.copy()
        self._public_ctx.make_context_public()  # retire la clé secrète de cette copie

    def get_public_context(self) -> ts.Context:
        return self._public_ctx

    def decrypt(self, serialized_vector: bytes, role: str) -> list:
        if role not in self.ALLOWED_DECRYPT_ROLES:
            raise HEAccessDenied(f"Role '{role}' is not authorized to decrypt HE values")
        vec = ts.ckks_vector_from(self._secret_ctx, serialized_vector)
        return vec.decrypt()


# Instance unique partagée par le service
he_manager = HEKeyManager()