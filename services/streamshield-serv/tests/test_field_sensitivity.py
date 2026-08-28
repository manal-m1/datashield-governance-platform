import asyncio

from detection.field_sensitivity_repository import load_field_sensitivity


async def main():
    sensitivity = await load_field_sensitivity()

    print("\n=== SENSIBILITES MONGODB ===")

    for field, level in sensitivity.items():
        print(f"{field:20} -> {level}")

    print(f"\nNombre de champs : {len(sensitivity)}")


if __name__ == "__main__":
    asyncio.run(main())