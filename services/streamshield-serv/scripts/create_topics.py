"""
StreamShield - Tâche 1
Crée les topics Kafka nécessaires au pipeline (section 2.2/2.3 du cahier des charges) :
  - raw-<domaine>          : données brutes publiées par les systèmes sources
  - risk-scores-<domaine>  : scores de risque calculés par la fenêtre glissante (Tâche 2)
  - protected-<domaine>    : données protégées après passage par EthiMask (Tâche 3)

Usage:
    python scripts/create_topics.py
    python scripts/create_topics.py --domain rh --partitions 6
"""
import argparse
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

import os
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# 7 jours de rétention -> permet de rejouer un flux en cas d'ajustement des seuils
RETENTION_MS = 7 * 24 * 60 * 60 * 1000

TOPIC_SUFFIXES = ["raw", "risk-scores", "protected"]


def build_topic_specs(domain: str, partitions: int, replication_factor: int) -> list[NewTopic]:
    specs = []
    for suffix in TOPIC_SUFFIXES:
        specs.append(
            NewTopic(
                name=f"{suffix}-{domain}",
                num_partitions=partitions,
                replication_factor=replication_factor,
                topic_configs={"retention.ms": str(RETENTION_MS)},
            )
        )
    return specs


def create_topics(domain: str, partitions: int = 6, replication_factor: int = 1):
    admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS, client_id="streamshield-admin")
    specs = build_topic_specs(domain, partitions, replication_factor)

    try:
        admin.create_topics(new_topics=specs, validate_only=False)
        for spec in specs:
            print(f"✅ Topic créé : {spec.name} ({partitions} partitions)")
    except TopicAlreadyExistsError:
        # Idempotent : relancer le script ne doit pas planter si les topics existent déjà
        existing = admin.list_topics()
        for spec in specs:
            status = "existe déjà" if spec.name in existing else "erreur inconnue"
            print(f"⚠️  {spec.name} : {status}")
    finally:
        admin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Création des topics Kafka StreamShield")
    parser.add_argument("--domain", default="clients", help="Domaine métier (ex: clients, rh, sante)")
    parser.add_argument("--partitions", type=int, default=6, help="Nombre de partitions par topic")
    parser.add_argument("--replication-factor", type=int, default=1, help="Facteur de réplication (1 en dev, 3 en prod)")
    args = parser.parse_args()

    print(f"\n🔧 Création des topics pour le domaine « {args.domain} »\n")
    create_topics(args.domain, args.partitions, args.replication_factor)