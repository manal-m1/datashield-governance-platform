"""
StreamShield - Injection d'événements de test
Envoie des événements dans raw-<domain> pour déclencher une détection et
vérifier la persistance MongoDB de bout en bout.

Usage:
    python -m scripts.produce_test_events --domain clients --count 60
"""
import argparse
import asyncio
import json
import os
import random
import uuid

from aiokafka import AIOKafkaProducer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

VILLES = ["Casablanca", "Rabat", "Fes", "Marrakech", "Tanger"]
SEXES = ["M", "F"]


async def produce(domain: str, count: int, inject_risky: bool):
    topic = f"raw-{domain}"
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    try:
        for i in range(count):
            event = {
                "event_id": str(uuid.uuid4()),
                "ville": random.choice(VILLES),
                "code_postal": random.choice(["20000", "10000", "30000", "40000"]),
                "sexe": random.choice(SEXES),
                "date_naissance": f"19{random.randint(60,99)}-0{random.randint(1,9)}-1{random.randint(0,9)}",
            }
            await producer.send_and_wait(topic, value=event)

        if inject_risky:
            risky = {
                "event_id": str(uuid.uuid4()),
                "ville": "Casablanca",
                "code_postal": "20500",
                "sexe": "F",
                "date_naissance": "1985-07-22",
            }
            for _ in range(3):
                await producer.send_and_wait(topic, value=risky)

        total = count + (3 if inject_risky else 0)
        print(f"{total} événements envoyés sur '{topic}'")
    finally:
        await producer.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="clients")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--inject-risky-combo", action="store_true", default=True)
    args = parser.parse_args()

    asyncio.run(produce(args.domain, args.count, args.inject_risky_combo))