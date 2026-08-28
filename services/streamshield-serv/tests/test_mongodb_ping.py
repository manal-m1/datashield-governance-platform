import asyncio

from backend.database.mongodb import db


async def main():
    result = await db.command("ping")
    print("MongoDB Atlas OK")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())