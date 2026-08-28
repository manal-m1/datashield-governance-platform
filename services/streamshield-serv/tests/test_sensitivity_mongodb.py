import asyncio

from detection.field_sensitivity_repository import (
    load_field_sensitivity,
)


async def main():

    print("\n=== APPEL 1 ===")
    data1 = await load_field_sensitivity()
    print(f"Nombre de champs : {len(data1)}")

    print("\n=== APPEL 2 ===")
    data2 = await load_field_sensitivity()
    print(f"Nombre de champs : {len(data2)}")

    print("\n=== ATTENTE 11s ===")
    await asyncio.sleep(11)

    print("\n=== APPEL 3 ===")
    data3 = await load_field_sensitivity()
    print(f"Nombre de champs : {len(data3)}")

    print("\n=== VERIFICATION ===")

    assert data1 == data2
    print("OK : Appel 2 utilise les mêmes données que l'appel 1.")

    assert data2 == data3
    print("OK : Appel 3 récupère les mêmes données après expiration du TTL.")

    print("\nTEST CACHE TTL TERMINE")


if __name__ == "__main__":
    asyncio.run(main())