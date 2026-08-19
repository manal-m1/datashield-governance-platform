# tests/test_mongodb_connection.py
import asyncio
from backend.database.mongodb import ping, db

async def test_connexion():
    await ping()
    print("✅ Connexion Atlas OK")
    print("Base utilisée :", db.name)
    print("Collections existantes :", await db.list_collection_names())

asyncio.run(test_connexion())