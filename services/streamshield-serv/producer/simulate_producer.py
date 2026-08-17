"""
StreamShield - Tâche 1
Producer de simulation : publie des enregistrements synthétiques (profil marocain) sur
le topic raw-<domaine>, avec un mélange volontaire de combinaisons de champs à risque
et de combinaisons peu discriminantes -- réutilisable comme jeu de données de
validation pour la Tâche 2 (section 4.5 du cahier des charges).

Usage:
    python producer/simulate_producer.py --domain clients --rate 50 --duration 120
"""
import argparse
import asyncio
import json
import random
import time
import uuid

from aiokafka import AIOKafkaProducer
from faker import Faker

fake = Faker("fr_FR")  # proche du contexte marocain pour noms/adresses francophones

import os
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

VILLES = ["Rabat", "Casablanca", "Salé", "Fès", "Marrakech", "Tanger", "Agadir"]

# Une poignée de "profils rares" volontairement réutilisés pour créer de vraies
# combinaisons à faible k(C) -- utile pour valider que la détection (Tâche 2)
# les retrouve bien.
RARE_PROFILES = [
    {"ville": "Salé", "code_postal": "11080", "sexe": "F", "date_naissance": "1990-02-14"},
    {"ville": "Agadir", "code_postal": "80000", "sexe": "M", "date_naissance": "1985-11-03"},
]


def make_record(inject_rare: bool) -> dict:
    if inject_rare and random.random() < 0.15:
        # ~15% des messages réutilisent un profil rare -> combinaison à risque garantie
        profile = random.choice(RARE_PROFILES)
    else:
        ville = random.choice(VILLES)
        profile = {
            "ville": ville,
            "code_postal": fake.postcode(),
            "sexe": random.choice(["M", "F"]),
            "date_naissance": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        }

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "nom": fake.name(),
        "email": fake.email(),
        "cin": fake.bothify(text="??######").upper(),
        "telephone": fake.phone_number(),
        "salaire": round(random.uniform(4000, 25000), 2),
        **profile,
    }


async def produce(domain: str, rate: int, duration: int, inject_rare: bool):
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        # clé = ville -> garantit que les événements d'une même zone atterrissent
        # sur la même partition, cohérent avec le partitionnement décrit en 2.3
        key_serializer=lambda k: k.encode("utf-8"),
    )
    await producer.start()
    topic = f"raw-{domain}"
    sent = 0
    interval = 1.0 / rate if rate > 0 else 0
    deadline = time.time() + duration

    try:
        print(f"▶️  Publication sur '{topic}' à ~{rate} msg/s pendant {duration}s...")
        while time.time() < deadline:
            record = make_record(inject_rare)
            await producer.send_and_wait(topic, value=record, key=record["ville"])
            sent += 1
            if sent % 100 == 0:
                print(f"   {sent} messages envoyés")
            await asyncio.sleep(interval)
    finally:
        await producer.stop()
        print(f"✅ Terminé : {sent} messages publiés sur '{topic}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Producer de simulation StreamShield")
    parser.add_argument("--domain", default="clients")
    parser.add_argument("--rate", type=int, default=20, help="Messages par seconde")
    parser.add_argument("--duration", type=int, default=60, help="Durée en secondes")
    parser.add_argument("--no-rare-profiles", action="store_true", help="Désactive l'injection de profils rares")
    args = parser.parse_args()

    asyncio.run(produce(args.domain, args.rate, args.duration, inject_rare=not args.no_rare_profiles))