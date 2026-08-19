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
import time
from typing import Dict

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from detection.sliding_window import PartitionedSlidingWindow
from detection.risk_scorer import RiskScorer
from detection.apriori_detector import AprioriCombinationDetector, DetectionConfig
from detection.threshold_manager import ThresholdManager, DEFAULT_THRESHOLD
from backend.database.mongodb import db

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

    # Champs candidats pour la détection de quasi-identifiants (section 4.4) --
    # ceux générés par le producer de simulation (nom/cin/email/telephone/salaire
    # exclus ici : ce sont des identifiants directs ou attributs sensibles,
    # pas des quasi-identifiants au sens de la doc).
    CANDIDATE_FIELDS = ("ville", "code_postal", "sexe", "date_naissance")

    def __init__(
        self,
        domain: str,
        group_id: str = CONSUMER_GROUP_ID,
        window_seconds: int = 60,
        detection_interval: int = 50,
    ):
        self.domain = domain
        self.topic = f"raw-{domain}"
        self.risk_topic = f"risk-scores-{domain}"
        self.group_id = group_id
        self.consumer: AIOKafkaConsumer | None = None
        self.risk_producer: AIOKafkaProducer | None = None
        self._stopping = asyncio.Event()
        self._processed_count = 0
        self._messages_since_detection: Dict[int, int] = {}
        self.detection_interval = detection_interval

        # Tâche 2 : fenêtre glissante, une par partition Kafka (section 2.4)
        self.window = PartitionedSlidingWindow(size_seconds=window_seconds)

        # Tâche 2 : seuil configurable par domaine, persisté MongoDB
        # (livrable "jeu de règles de seuils configurables")
        self.threshold_manager = ThresholdManager(db)
        self.scorer = RiskScorer(threshold=DEFAULT_THRESHOLD)  # valeur réelle chargée dans start()
        self.detector = AprioriCombinationDetector(
            self.scorer,
            DetectionConfig(candidate_fields=self.CANDIDATE_FIELDS, prune_threshold=0.15, max_depth=4),
        )
        self._detections_since_threshold_refresh = 0

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            enable_auto_commit=False,       # commit manuel -> contrôle total du at-least-once
            auto_offset_reset="earliest",   # au premier démarrage, ne pas sauter l'historique
            max_poll_records=500,
        )
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                await self.consumer.start()
                break
            except KafkaConnectionError as e:
                logger.warning(f"Kafka pas encore prêt (tentative {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise
                await asyncio.sleep(3)
        await self.consumer.start()

        # Tâche 2 : producer dédié à la publication des événements de risque
        self.risk_producer = AIOKafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.risk_producer.start()

        # Charge le vrai seuil configuré pour ce domaine (livrable seuils configurables)
        self.scorer.threshold = await self.threshold_manager.get_threshold(self.domain)

        logger.info(
            f"Consumer démarré sur '{self.topic}' (group_id={self.group_id}, "
            f"seuil de risque={self.scorer.threshold})"
        )

    async def stop(self):
        self._stopping.set()
        if self.consumer:
            await self.consumer.stop()
        if self.risk_producer:
            await self.risk_producer.stop()
        logger.info(f"Consumer arrêté proprement. Total traité : {self._processed_count}")

    async def process_record(self, record: dict, partition: int, offset: int, kafka_timestamp: int):
        """
        Chaque enregistrement alimente la fenêtre glissante de sa partition
        (Tâche 2) -- c'est ici que le futur calcul de risque de combinaison
        de quasi-identifiants viendra lire les données accumulées.

        Trace d'audit (user story data steward) : CHAQUE message est journalisé
        individuellement avec son topic, sa partition, son offset et l'horodatage
        Kafka -- pas seulement un compteur périodique -- pour rester traçable
        jusqu'à l'origine exacte en cas d'audit.
        """
        self._processed_count += 1
        # Horodatage de TRAITEMENT (pas l'horodatage Kafka) : pendant un rattrapage
        # de backlog (comme lors des tests de résilience de la Tâche 1), les messages
        # peuvent avoir un kafka_ts vieux de plusieurs minutes -- la fenêtre doit
        # refléter "ce qui arrive maintenant", pas l'ancienneté de l'événement source.
        self.window.add(partition, record)

        logger.info(
            f"AUDIT topic={self.topic} partition={partition} offset={offset} "
            f"kafka_ts={kafka_timestamp} event_id={record.get('event_id', 'n/a')} "
            f"window_size={self.window.window_size(partition)}"
        )
        if self._processed_count % 100 == 0:
            logger.info(f"[{self.topic}] {self._processed_count} messages traités au total")

        # Tâche 2 : déclenche la détection tous les N messages de CETTE partition
        # (pas à chaque message -- coûteux inutilement ; pas non plus sur un timer
        # séparé pour rester simple : la fréquence suit le débit réel du flux).
        self._messages_since_detection[partition] = self._messages_since_detection.get(partition, 0) + 1
        if self._messages_since_detection[partition] >= self.detection_interval:
            self._messages_since_detection[partition] = 0
            await self._run_detection(partition)

    async def _run_detection(self, partition: int):
        """
        Exécute le détecteur Apriori sur la fenêtre courante de la partition,
        et publie chaque combinaison à risque sur risk-scores-<domaine>
        (section 4.4, point 5 du cahier des charges), en la persistant aussi
        dans MongoDB pour que l'API puisse l'exposer (user story administrateur
        : "je veux visualiser les combinaisons jugées à risque").
        """
        # Rafraîchit le seuil périodiquement (toutes les 10 détections) --
        # permet à un ajustement fait via l'API de prendre effet sans
        # redémarrer le consumer (user story administrateur : ajuster le seuil).
        self._detections_since_threshold_refresh += 1
        if self._detections_since_threshold_refresh >= 10:
            self._detections_since_threshold_refresh = 0
            new_threshold = await self.threshold_manager.get_threshold(self.domain)
            if new_threshold != self.scorer.threshold:
                logger.info(f"Seuil mis à jour pour '{self.domain}': {self.scorer.threshold} -> {new_threshold}")
                self.scorer.threshold = new_threshold

        records = self.window.get_records(partition)
        triggered = self.detector.triggered_only(records)

        if not triggered:
            return

        for result in triggered:
            event = {
                "domain": self.domain,
                "partition": partition,
                "fields": list(result.fields),
                "score": round(result.score, 4),
                "k": result.k,
                "uniqueness": round(result.uniqueness, 4),
                "sample_size": result.sample_size,
                "window_size": len(records),
            }
            await self.risk_producer.send_and_wait(self.risk_topic, value=event)

            if db is not None:
                await db.streamshield_risk_events.insert_one({**event, "timestamp": time.time()})

            logger.warning(
                f"RISK DETECTED fields={result.fields} score={round(result.score, 3)} "
                f"k={result.k} partition={partition} -> publié sur '{self.risk_topic}'"
            )

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
                            await self.process_record(msg.value, tp.partition, msg.offset, msg.timestamp)
                        # Commit après traitement complet du lot de cette partition
                        if messages:
                            await self.consumer.commit({tp: messages[-1].offset + 1})
                except KafkaConnectionError as e:
                    logger.warning(f"Connexion Kafka perdue ({e}) -- nouvelle tentative dans 5s")
                    await asyncio.sleep(5)
        finally:
            await self.stop()

async def main(domain: str, group_id: str, window_seconds: int, detection_interval: int):
    consumer = StreamShieldConsumer(
        domain, group_id=group_id, window_seconds=window_seconds, detection_interval=detection_interval
    )

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
    parser.add_argument(
        "--group-id",
        default=CONSUMER_GROUP_ID,
        help="Group ID Kafka -- utilise un nom distinct (ex: streamshield-detection-test) "
             "pour des tests manuels sans perturber le service persistant.",
    )
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=60,
        help="Taille de la fenêtre glissante en secondes (Tâche 2, section 2.4)",
    )
    parser.add_argument(
        "--detection-interval",
        type=int,
        default=50,
        help="Nombre de messages entre deux exécutions du détecteur, par partition",
    )
    args = parser.parse_args()

    asyncio.run(main(args.domain, args.group_id, args.window_seconds, args.detection_interval))