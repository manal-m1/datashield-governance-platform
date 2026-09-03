import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "DataGovDB")

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI manquant — vérifier que .env racine est bien chargé (env_file)"
    )

client = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)

db = client[DB_NAME]

# ============================================================================
# Collections StreamShield (propres)
# ============================================================================

risk_events_collection = db["streamshield_risk_events"]
thresholds_collection = db["streamshield_thresholds"]
field_sensitivity_collection = db["streamshield_field_sensitivity"]
fuzzy_config_collection = db["streamshield_fuzzy_config"]
fuzzy_rules_collection = db["streamshield_fuzzy_rules"]
risk_scores_collection = db["streamshield_risk_scores"]

# ============================================================================
# Collections partagées avec cleaning-service (même base DataGovDB)
# Lecture seule — StreamShield ne modifie jamais ces datasets
# ============================================================================

raw_datasets_collection = db["raw_datasets"]
clean_datasets_collection = db["clean_datasets"]


async def ping():
    await client.admin.command("ping")
