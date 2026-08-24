import asyncio
from backend.database.mongodb import ping, db


def test_connexion():
    async def _check():
        await ping()
        assert db.name is not None

    asyncio.run(_check())