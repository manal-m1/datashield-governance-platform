"""
StreamShield - Tâche 1
Consumer d'ingestion : lit en continu le(s) topic(s) raw-<domaine>, avec :
  - commit manuel des offsets APRÈS traitement complet (garantie at-least-once)
  - reprise automatique sans perte ni duplication après un redémarrage
  - un point d'extension clair pour brancher la fenêtre glissante de la Tâche 2

Usage:
    python consumer/main.py --domain clients
"""
import argparse
import asyncio
import json
import logging
import signal

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("streamshield.consumer")

import os
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP_ID = "streamshield-detection"


class StreamShieldConsumer:
    """
    Consumer group : streamshield-detection (cf. section 2.4 du cahier des charges).

    Le commit manuel après traitement garantit qu'un message n'est jamais marqué
    comme "lu" tant que son traitement (ici : simple log, demain : mise à jour de
    la fenêtre glissante de la Tâche 2) n'est pas terminé -- c'est la propriété
    at-least-once attendue par le KPI "0% de perte de messages" (section 3.6).
    """

    def __init__(self, domain: str):
        self.domain = domain
        self.topic = f"raw-{domain}"
        self.consumer: AIOKafkaConsumer | None = None
        self._stopping = asyncio.Event()
        self._processed_count = 0

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            enable_auto_commit=False,       # commit manuel -> contrôle total du at-least-once
            auto_offset_reset="earliest",   # au premier démarrage, ne pas sauter l'historique
            max_poll_records=500,
        )
        await self.consumer.start()
        logger.info(f"Consumer démarré sur '{self.topic}' (group_id={CONSUMER_GROUP_ID})")

    async def stop(self):
        self._stopping.set()
        if self.consumer:
            await self.consumer.stop()
        logger.info(f"Consumer arrêté proprement. Total traité : {self._processed_count}")

    async def process_record(self, record: dict, partition: int):
        """
        Point d'extension pour la Tâche 2 : c'est ici que chaque enregistrement
        sera injecté dans la fenêtre glissante par clé de partition, pour le
        calcul du score de risque de combinaison de quasi-identifiants.
        Pour l'instant (Tâche 1), on se contente de logger et de compter.
        """
        self._processed_count += 1
        if self._processed_count % 100 == 0:
            logger.info(f"[{self.topic}] {self._processed_count} messages traités (dernier: partition {partition})")

    async def run(self):
        """
        Boucle principale avec reprise automatique : toute erreur de connexion Kafka
        est absorbée et la lecture reprend après un court délai, sans crash du process
        ni perte d'offset (puisque rien n'est commité tant que le message n'est pas traité).
        """
        await self.start()
        try:
            while not self._stopping.is_set():
                try:
                    result = await self.consumer.getmany(timeout_ms=1000, max_records=500)
                    for tp, messages in result.items():
                        for msg in messages:
                            await self.process_record(msg.value, tp.partition)
                        # Commit après traitement complet du lot de cette partition
                        if messages:
                            await self.consumer.commit({tp: messages[-1].offset + 1})
                except KafkaConnectionError as e:
                    logger.warning(f"Connexion Kafka perdue ({e}) -- nouvelle tentative dans 5s")
                    await asyncio.sleep(5)
        finally:
            await self.stop()


async def main(domain: str):
    consumer = StreamShieldConsumer(domain)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Signal d'arrêt reçu, fermeture en cours...")
        stop_event.set()
        consumer._stopping.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    await consumer.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consumer d'ingestion StreamShield")
    parser.add_argument("--domain", default="clients")
    args = parser.parse_args()

    asyncio.run(main(args.domain))