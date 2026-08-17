"""
StreamShield - Test de connectivité Kafka (HDP Sandbox)
Vérifie que le service peut réellement dialoguer avec le broker,
pas juste ouvrir un socket TCP.

Usage:
    python scripts/test_kafka_connection.py
"""
import os
from kafka import KafkaAdminClient, KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def test_connection():
    print(f"🔌 Tentative de connexion à : {BOOTSTRAP_SERVERS}")

    try:
        admin = KafkaAdminClient(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            client_id="streamshield-test",
            request_timeout_ms=10000,
        )
        print("✅ Connexion admin établie")

        topics = admin.list_topics()
        print(f"✅ {len(topics)} topic(s) trouvé(s) sur le broker :")
        for t in sorted(topics):
            print(f"   - {t}")

        admin.close()

    except NoBrokersAvailable:
        print("❌ Aucun broker disponible à cette adresse.")
        print("   Vérifie : le sandbox est démarré ? le port 6667 est bien celui de Kafka ?")
        return False
    except KafkaError as e:
        print(f"❌ Erreur Kafka : {e}")
        print("   Si l'erreur mentionne une version d'API, il faudra fixer api_version explicitement.")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue : {type(e).__name__}: {e}")
        return False

    return True


if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)