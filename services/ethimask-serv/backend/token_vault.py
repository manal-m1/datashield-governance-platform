"""
Token Vault - Tokenization avec stockage séparé et chiffré.
Le mapping token -> valeur réelle vit dans sa propre collection Mongo,
jamais mêlée aux autres données du service.
"""
import uuid
import os
from datetime import datetime
from cryptography.fernet import Fernet

VAULT_KEY_ENV = os.getenv("VAULT_ENCRYPTION_KEY")
if not VAULT_KEY_ENV:
    raise RuntimeError(
        "VAULT_ENCRYPTION_KEY environment variable is required. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
fernet = Fernet(VAULT_KEY_ENV.encode())

ALLOWED_DETOKENIZE_ROLES = {"admin", "steward"}


class TokenVault:
    def __init__(self, db):
        self.collection = db.token_vault if db is not None else None

    async def tokenize(self, value: str, entity_type: str) -> str:
        token = f"TOK_{uuid.uuid4().hex}"
        if self.collection is not None:
            await self.collection.insert_one({
                "token": token,
                "entity_type": entity_type,
                "value_enc": fernet.encrypt(value.encode()).decode(),
                "created_at": datetime.now().isoformat()
            })
        return token

    async def detokenize(self, token: str, role: str) -> str:
        if role not in ALLOWED_DETOKENIZE_ROLES:
            raise PermissionError(f"Role '{role}' is not authorized to detokenize")
        if self.collection is None:
            raise RuntimeError("Vault not connected")
        doc = await self.collection.find_one({"token": token})
        if not doc:
            raise KeyError("Token not found")
        return fernet.decrypt(doc["value_enc"].encode()).decode()