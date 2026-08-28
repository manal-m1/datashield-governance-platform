"""
StreamShield - Tâche 1 + Tâche 2 (v2 - corrigée après revue)
Consumer d'ingestion : lit en continu le(s) topic(s) raw-<domaine>, avec :
  - commit manuel des offsets APRÈS traitement complet (garantie at-least-once)
  - reprise automatique sans perte ni duplication après un redémarrage
  - retry de connexion au démarrage (Kafka pas encore prêt)
  - déclenchement de détection MIXTE : tous les N messages OU toutes les
    X secondes, le premier des deux critères atteint (v2)

CHANGEMENTS v2 :
  - Suppression du double appel à self.consumer.start() (bug résiduel de
    la fusion avec la logique de retry).
  - Déclenchement mixte de _run_detection : l'ancien mécanisme (uniquement
    "tous les detection_interval messages") pouvait créer une latence
    arbitrairement longue à faible débit -- si une partition ne reçoit que
    quelques messages par minute, il fallait potentiellement des dizaines
    de minutes avant la première détection. On ajoute donc un déclenchement
    par temps écoulé (detection_max_interval_seconds) en complément.

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
from detection.field_sensitivity_repository import load_field_sensitivity
from detection.sliding_window import PartitionedSlidingWindow
from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.combination_detector import CombinationDetector, DetectionConfig
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
    """

    CANDIDATE_FIELDS = (
    "ville",
    "code_postal",
    "sexe",
    "date_naissance",
    "age",
    "sex",
    "race",
    "native_country",
    "education",
)

    def __init__(
        self,
        domain: str,
        group_id: str = CONSUMER_GROUP_ID,
        window_seconds: int = 60,
        detection_interval: int = 50,
        detection_max_interval_seconds: int = 15,
        window_max_size: int = 50_000,
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

        # v2 : déclenchement mixte -- borne la latence max même à faible débit
        self.detection_max_interval_seconds = detection_max_interval_seconds
        self._last_detection_time: Dict[int, float] = {}

        self.window = PartitionedSlidingWindow(size_seconds=window_seconds, max_size=window_max_size)

        self.threshold_manager = ThresholdManager(db)

        self.field_sensitivity = {}
        self.scorer = FuzzyRiskScorer(
            threshold=DEFAULT_THRESHOLD,
            field_sensitivity=self.field_sensitivity,)
        self.detector = CombinationDetector(
            self.scorer,
            DetectionConfig(candidate_fields=self.CANDIDATE_FIELDS, max_depth=4),
        )
        self._detections_since_threshold_refresh = 0

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            max_poll_records=500,
        )

        # Retry de connexion -- Kafka peut ne pas être prêt au tout premier
        # démarrage même avec un healthcheck (fenêtre de course résiduelle).
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                await self.consumer.start()
                break  # v2 : plus de second appel après la boucle
            except KafkaConnectionError as e:
                logger.warning(f"Kafka pas encore prêt (tentative {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise
                await asyncio.sleep(3)

        self.risk_producer = AIOKafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.risk_producer.start()
        self.scorer.threshold = await self.threshold_manager.get_threshold(
        self.domain
        )
        self.scorer.field_sensitivity = await load_field_sensitivity()
        await self.scorer.load_fuzzy_configuration()
        logger.info(
            f"Consumer démarré sur '{self.topic}' "
            f"(group_id={self.group_id}, "
            f"seuil de risque={self.scorer.threshold}, "
            f"champs de sensibilité chargés="
            f"{len(self.scorer.field_sensitivity)}, "
            f"règles fuzzy chargées={len(self.scorer.fuzzy_rules)}, "
            f"déclenchement={self.detection_interval} msgs OU "
            f"{self.detection_max_interval_seconds}s)"
        )
        # Chargement de la configuration et des règles fuzzy depuis MongoDB
        

    async def stop(self):
        self._stopping.set()
        if self.consumer:
            await self.consumer.stop()
        if self.risk_producer:
            await self.risk_producer.stop()
        logger.info(f"Consumer arrêté proprement. Total traité : {self._processed_count}")

    async def process_record(self, record: dict, partition: int, offset: int, kafka_timestamp: int):
        self._processed_count += 1

        # v2 : on enrichit le record avec kafka_timestamp avant de l'ajouter à la
        # fenêtre, pour pouvoir le retrouver plus tard dans _run_detection (audit
        # complet -- distinguer "quand l'événement source a eu lieu côté Kafka" de
        # "quand StreamShield l'a traité"). Le préfixe "_" signale que ce n'est PAS
        # un champ candidat pour le calcul de risque, juste une métadonnée technique.
        enriched_record = {**record, "_kafka_timestamp": kafka_timestamp}
        self.window.add(partition, enriched_record)

        logger.info(
            f"AUDIT topic={self.topic} partition={partition} offset={offset} "
            f"kafka_ts={kafka_timestamp} event_id={record.get('event_id', 'n/a')} "
            f"window_size={self.window.window_size(partition)}"
        )
        if self._processed_count % 100 == 0:
            logger.info(f"[{self.topic}] {self._processed_count} messages traités au total")

        self._messages_since_detection[partition] = (
        self._messages_since_detection.get(partition, 0) + 1
        )

        now = time.time()

        # Première réception sur cette partition :
        # on initialise l'horloge de détection sans déclencher immédiatement.
        if partition not in self._last_detection_time:
            self._last_detection_time[partition] = now

        last_detection = self._last_detection_time[partition]

        count_trigger = (
            self._messages_since_detection[partition]
            >= self.detection_interval
        )

        time_trigger =(
            (now - last_detection)m
            >= self.detection_max_interval_seconds
            and self.window.window_size(partition) > 0
        )
        if count_trigger or time_trigger:
            self._messages_since_detection[partition] = 0
            self._last_detection_time[partition] = now
            reason = "count" if count_trigger else "timeout"
            logger.debug(f"Détection déclenchée sur partition {partition} (raison={reason})")
            await self._run_detection(partition)

    async def _run_detection(self, partition: int):
        self._detections_since_threshold_refresh += 1
        if self._detections_since_threshold_refresh >= 10:
            self._detections_since_threshold_refresh = 0
            new_threshold = await self.threshold_manager.get_threshold(self.domain)
            if new_threshold != self.scorer.threshold:
                logger.info(f"Seuil mis à jour pour '{self.domain}': {self.scorer.threshold} -> {new_threshold}")
                self.scorer.threshold = new_threshold

        # records = self.window.get_records(partition)
        # triggered = self.detector.triggered_only(records)

        # if not triggered:
        #     return
        records = self.window.get_records(partition)
        logger.info(
            f"DETECTION | partition={partition} | "
            f"records={len(records)}"
        )

        triggered = self.detector.triggered_only(records)

        logger.info(
            f"DETECTION RESULT | "
            f"partition={partition} | "
            f"triggered={len(triggered)}"
            )

        if not triggered:
            logger.info(
                    f"NO RISK DETECTED | partition={partition}"
                )
            return
        # v2 : horodatage Kafka le plus récent de la fenêtre -- repère
        # approximatif de "quand côté source", en plus du timestamp de
        # traitement déjà utilisé (traçabilité d'audit complète)
        kafka_timestamps = [r.get("_kafka_timestamp") for r in records if r.get("_kafka_timestamp") is not None]
        latest_kafka_ts = max(kafka_timestamps) if kafka_timestamps else None

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
                await db.streamshield_risk_events.insert_one({
                    **event,
                    "processing_timestamp": time.time(),   # v2 : renommé (était "timestamp")
                    "kafka_timestamp_ms": latest_kafka_ts,  # v2 : nouveau champ d'audit
                })

            logger.warning(
                f"RISK DETECTED fields={result.fields} score={round(result.score, 3)} "
                f"k={result.k} partition={partition} -> publié sur '{self.risk_topic}'"
            )
    async def run(self):
        await self.start()
        try:
            while not self._stopping.is_set():
                try:
                    result = await self.consumer.getmany(timeout_ms=1000, max_records=500)
                    for tp, messages in result.items():
                        for msg in messages:
                            await self.process_record(msg.value, tp.partition, msg.offset, msg.timestamp)
                        if messages:
                            await self.consumer.commit({tp: messages[-1].offset + 1})
                except KafkaConnectionError as e:
                    logger.warning(f"Connexion Kafka perdue ({e}) -- nouvelle tentative dans 5s")
                    await asyncio.sleep(5)
        finally:
            await self.stop()


async def main(domain: str, group_id: str, window_seconds: int, detection_interval: int, detection_max_interval_seconds: int):
    consumer = StreamShieldConsumer(
        domain, group_id=group_id, window_seconds=window_seconds,
        detection_interval=detection_interval,
        detection_max_interval_seconds=detection_max_interval_seconds,
    )

    loop = asyncio.get_running_loop()

    def _handle_signal():
        logger.info("Signal d'arrêt reçu, fermeture en cours...")
        consumer._stopping.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    await consumer.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consumer d'ingestion StreamShield")
    parser.add_argument("--domain", default="clients")
    parser.add_argument("--group-id", default=CONSUMER_GROUP_ID)
    parser.add_argument("--window-seconds", type=int, default=60)
    parser.add_argument("--detection-interval", type=int, default=50)
    parser.add_argument(
        "--detection-max-interval-seconds", type=int, default=15,
        help="Déclenche la détection après ce délai même sans atteindre detection-interval (v2)",
    )
    args = parser.parse_args()

    asyncio.run(main(
        args.domain, args.group_id, args.window_seconds,
        args.detection_interval, args.detection_max_interval_seconds,
    ))