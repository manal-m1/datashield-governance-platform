import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "datagov")  # même nom de base que les autres services

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI manquant — vérifier que .env racine est bien chargé (env_file)")

client = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)
db = client[DB_NAME]

# Collections StreamShield
risk_events_collection = db["streamshield_risk_events"]
thresholds_collection = db["streamshield_thresholds"]

async def ping():
    await client.admin.command("ping")