"""
StreamShield - Tâche 1 + Tâche 2 (v2)
Consumer d'ingestion Kafka.

Fonctionnalités :
  - commit manuel après traitement complet
  - garantie at-least-once
  - reprise après redémarrage
  - retry de connexion Kafka
  - détection mixte :
        * tous les N messages
        * OU toutes les X secondes
  - métriques Prometheus :
        * messages traités
        * consumer lag
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import time
from typing import Dict

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from prometheus_client import Counter, Gauge

from detection.field_sensitivity_repository import load_field_sensitivity
from detection.sliding_window import PartitionedSlidingWindow
from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.combination_detector import CombinationDetector, DetectionConfig
from detection.threshold_manager import ThresholdManager, DEFAULT_THRESHOLD
from detection.candidate_field_selector import select_candidate_fields

from backend.database.mongodb import db
from backend.clients.ethimask_client import EthiMaskClient


# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("streamshield.consumer")


# ============================================================================
# ENVIRONMENT
# ============================================================================

BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092"
)

CONSUMER_GROUP_ID = "streamshield-detection"


# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

kafka_messages_processed = Counter(
    "streamshield_kafka_messages_processed_total",
    "Nombre de messages Kafka traités avec succès par StreamShield",
    ["topic"]
)
kafka_consumer_lag = Gauge(
    "streamshield_kafka_consumer_lag",
    "Lag du consumer Kafka StreamShield",
    ["topic", "partition"]
)


# ============================================================================
# SAFE JSON DESERIALIZER
# ============================================================================

def safe_json_deserializer(v):
    """
    Désérialise un message Kafka JSON sans faire tomber le consumer
    lorsqu'un message est vide ou invalide.
    """

    if v is None:
        logger.error(
            "MESSAGE KAFKA INVALIDE : valeur None"
        )
        return None

    try:
        raw = v.decode("utf-8").strip()

        if not raw:
            logger.error(
                "MESSAGE KAFKA INVALIDE : valeur vide"
            )
            return None

        return json.loads(raw)

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:

        logger.error(
            "MESSAGE KAFKA INVALIDE : %s | contenu=%r",
            exc,
            v[:200] if v else v
        )

        return None


# ============================================================================
# CONSUMER
# ============================================================================

class StreamShieldConsumer:
    """
    Consumer Kafka StreamShield.

    Consumer group :
        streamshield-detection
    """

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

        # Détection temporelle
        self.detection_max_interval_seconds = (
            detection_max_interval_seconds
        )

        self.min_detection_window_size = 20

        self._last_detection_time: Dict[int, float] = {}

        # Fenêtre glissante
        self.window = PartitionedSlidingWindow(
            size_seconds=window_seconds,
            max_size=window_max_size
        )

        # Gestion du seuil
        self.threshold_manager = ThresholdManager(db)

        self.field_sensitivity = {}

        self.scorer = FuzzyRiskScorer(
            threshold=DEFAULT_THRESHOLD,
            field_sensitivity=self.field_sensitivity,
        )

        # EthiMask
        self.ethimask_client = EthiMaskClient()

        # Refresh seuil
        self._detections_since_threshold_refresh = 0

    # ========================================================================
    # START
    # ========================================================================

    async def start(self):

        self.consumer = AIOKafkaConsumer(
            self.topic,

            bootstrap_servers=BOOTSTRAP_SERVERS,

            group_id=self.group_id,

            value_deserializer=safe_json_deserializer,

            key_deserializer=lambda k:
                k.decode("utf-8") if k else None,

            enable_auto_commit=False,

            auto_offset_reset="earliest",

            max_poll_records=500,
        )

        # --------------------------------------------------------------------
        # Retry Kafka
        # --------------------------------------------------------------------

        max_retries = 10

        for attempt in range(1, max_retries + 1):

            try:

                await self.consumer.start()

                logger.info(
                    "Connexion Kafka réussie "
                    "(tentative %s/%s)",
                    attempt,
                    max_retries
                )

                break

            except KafkaConnectionError as exc:

                logger.warning(
                    "Kafka pas encore prêt "
                    "(tentative %s/%s): %s",
                    attempt,
                    max_retries,
                    exc
                )

                if attempt == max_retries:
                    raise

                await asyncio.sleep(3)

        # --------------------------------------------------------------------
        # Risk producer
        # --------------------------------------------------------------------

        self.risk_producer = AIOKafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v:
                json.dumps(v).encode("utf-8"),
        )

        await self.risk_producer.start()

        # --------------------------------------------------------------------
        # Chargement configuration
        # --------------------------------------------------------------------

        self.scorer.threshold = (
            await self.threshold_manager.get_threshold(
                self.domain
            )
        )

        self.scorer.field_sensitivity = (
            await load_field_sensitivity()
        )

        await self.scorer.load_fuzzy_configuration()

        logger.info(
            "Consumer démarré sur '%s' "
            "(group_id=%s, seuil=%s, "
            "champs de sensibilité chargés=%s, "
            "règles fuzzy chargées=%s, "
            "déclenchement=%s msgs OU %ss)",
            self.topic,
            self.group_id,
            self.scorer.threshold,
            len(self.scorer.field_sensitivity),
            len(self.scorer.fuzzy_rules),
            self.detection_interval,
            self.detection_max_interval_seconds,
        )

        # --------------------------------------------------------------------
        # EthiMask health check
        # --------------------------------------------------------------------

        ethimask_available = (
            await self.ethimask_client.health_check()
        )

        if ethimask_available:
            logger.info(
                "EthiMask disponible"
            )
        else:
            logger.warning(
                "EthiMask indisponible"
            )

    # ========================================================================
    # ETHIMASK DETECTIONS
    # ========================================================================

    def _build_ethimask_detections(
        self,
        record: Dict,
        fields,
    ) -> list:

        detections = []

        for field in fields:

            if field not in record:
                continue

            sensitivity = (
                self.scorer.field_sensitivity.get(
                    field,
                    0.5
                )
            )

            if sensitivity >= 0.75:
                sensitivity_level = "critical"

            elif sensitivity >= 0.5:
                sensitivity_level = "high"

            elif sensitivity >= 0.25:
                sensitivity_level = "medium"

            else:
                sensitivity_level = "low"

            detections.append({
                "field": field,
                "value": record[field],
                "entity_type": field,
                "sensitivity_level": sensitivity_level,
                "confidence": 1.0,
            })

        return detections

    # ========================================================================
    # UPDATE CONSUMER LAG
    # ========================================================================
    async def update_consumer_lag(self):
        """
        Calcule le vrai consumer-group lag :

            end_offset - committed_offset

        Le committed offset correspond à l'offset réellement validé
        par le consumer group.
        """

        if self.consumer is None:
            return

        try:

            assignments = self.consumer.assignment()

            if not assignments:
                return

            end_offsets = await self.consumer.end_offsets(
                assignments
            )

            for tp in assignments:

                committed = await self.consumer.committed(tp)

                end_offset = end_offsets.get(tp)

                if committed is None:
                    continue

                if end_offset is None:
                    continue

                lag = max(
                    0,
                    end_offset - committed
                )

                kafka_consumer_lag.labels(
                    topic=tp.topic,
                    partition=str(tp.partition)
                ).set(lag)

                logger.debug(
                    "KAFKA LAG | topic=%s | partition=%s | "
                    "committed=%s | end=%s | lag=%s",
                    tp.topic,
                    tp.partition,
                    committed,
                    end_offset,
                    lag
                )

        except Exception as exc:

            logger.warning(
                "Impossible de mettre à jour le lag Kafka: %s",
                exc
            )

    # ========================================================================
    # STOP
    # ========================================================================

    async def stop(self):

        self._stopping.set()

        if self.consumer:

            try:
                await self.consumer.stop()

            except Exception as exc:

                logger.warning(
                    "Erreur lors de l'arrêt du consumer Kafka: %s",
                    exc
                )

        if self.risk_producer:

            try:
                await self.risk_producer.stop()

            except Exception as exc:

                logger.warning(
                    "Erreur lors de l'arrêt du producer Kafka: %s",
                    exc
                )

        logger.info(
            "Consumer arrêté proprement. Total traité : %s",
            self._processed_count
        )

    # ========================================================================
    # PROCESS RECORD
    # ========================================================================

    async def process_record(
        self,
        record: dict,
        partition: int,
        offset: int,
        kafka_timestamp: int
    ):

        self._processed_count += 1

        enriched_record = {
            **record,
            "_kafka_timestamp": kafka_timestamp
        }

        self.window.add(
            partition,
            enriched_record
        )

        logger.info(
            "AUDIT topic=%s partition=%s offset=%s "
            "kafka_ts=%s event_id=%s window_size=%s",
            self.topic,
            partition,
            offset,
            kafka_timestamp,
            record.get("event_id", "n/a"),
            self.window.window_size(partition)
        )

        if self._processed_count % 100 == 0:

            logger.info(
                "[%s] %s messages traités au total",
                self.topic,
                self._processed_count
            )

        # --------------------------------------------------------------------
        # Detection counters
        # --------------------------------------------------------------------

        self._messages_since_detection[partition] = (
            self._messages_since_detection.get(
                partition,
                0
            ) + 1
        )

        now = time.time()

        if partition not in self._last_detection_time:

            self._last_detection_time[partition] = now

        last_detection = (
            self._last_detection_time[partition]
        )

        count_trigger = (
            self._messages_since_detection[partition]
            >= self.detection_interval
        )

        current_window_size = (
            self.window.window_size(partition)
        )

        time_trigger = (
            (now - last_detection)
            >= self.detection_max_interval_seconds
            and current_window_size
            >= self.min_detection_window_size
        )

        # --------------------------------------------------------------------
        # Trigger
        # --------------------------------------------------------------------

        if count_trigger or time_trigger:

            self._messages_since_detection[partition] = 0

            self._last_detection_time[partition] = now

            reason = (
                "count"
                if count_trigger
                else "timeout"
            )

            logger.info(
                "Détection déclenchée sur partition %s "
                "(raison=%s, window_size=%s)",
                partition,
                reason,
                current_window_size
            )

            await self._run_detection(partition)

    # ========================================================================
    # RUN DETECTION
    # ========================================================================

    async def _run_detection(self, partition: int):

        self._detections_since_threshold_refresh += 1

        # --------------------------------------------------------------------
        # Refresh threshold
        # --------------------------------------------------------------------

        if self._detections_since_threshold_refresh >= 10:

            self._detections_since_threshold_refresh = 0

            new_threshold = (
                await self.threshold_manager.get_threshold(
                    self.domain
                )
            )

            if new_threshold != self.scorer.threshold:

                logger.info(
                    "Seuil mis à jour pour '%s': %s -> %s",
                    self.domain,
                    self.scorer.threshold,
                    new_threshold
                )

                self.scorer.threshold = new_threshold

        # --------------------------------------------------------------------
        # Get records
        # --------------------------------------------------------------------

        records = self.window.get_records(partition)

        if not records:

            logger.warning(
                "Aucun record disponible pour la détection | partition=%s",
                partition
            )

            return

        # --------------------------------------------------------------------
        # Candidate fields
        # --------------------------------------------------------------------

        candidate_fields = select_candidate_fields(
            records,
            max_candidates=12
        )

        logger.info(
            "CHAMPS CANDIDATS | partition=%s | fields=%s",
            partition,
            candidate_fields
        )

        if not candidate_fields:

            logger.warning(
                "Aucun champ QI candidat trouvé | partition=%s",
                partition
            )

            return

        # --------------------------------------------------------------------
        # Combination detection
        # --------------------------------------------------------------------

        config = DetectionConfig(
            candidate_fields=candidate_fields,
            max_depth=2
        )

        detector = CombinationDetector(
            scorer=self.scorer,
            config=config
        )

        triggered = detector.triggered_only(
            records
        )

        logger.info(
            "DETECTION RESULT | partition=%s | "
            "records=%s | triggered=%s",
            partition,
            len(records),
            len(triggered)
        )

        if not triggered:

            logger.info(
                "NO RISK DETECTED | partition=%s",
                partition
            )

            return

        # --------------------------------------------------------------------
        # Kafka timestamp
        # --------------------------------------------------------------------

        kafka_timestamps = [
            r.get("_kafka_timestamp")
            for r in records
            if r.get("_kafka_timestamp") is not None
        ]

        latest_kafka_ts = (
            max(kafka_timestamps)
            if kafka_timestamps
            else None
        )

        # --------------------------------------------------------------------
        # Risk combinations
        # --------------------------------------------------------------------

        for result in triggered:

            risky_fields = list(
                result.fields
            )

            logger.warning(
                "RISQUE DETECTE | partition=%s | "
                "fields=%s | score=%.4f | k=%s",
                partition,
                risky_fields,
                result.score,
                result.k
            )

            # ----------------------------------------------------------------
            # EthiMask preparation
            # ----------------------------------------------------------------

            ethimask_requests = []

            for record in records:

                detections = (
                    self._build_ethimask_detections(
                        record,
                        risky_fields
                    )
                )

                if not detections:
                    continue

                ethimask_requests.append({
                    "data": record,
                    "detections": detections,
                })

            logger.info(
                "ETHIMASK PREPARATION | partition=%s | "
                "fields=%s | records=%s",
                partition,
                risky_fields,
                len(ethimask_requests)
            )

            # ----------------------------------------------------------------
            # Risk event
            # ----------------------------------------------------------------

            event = {
                "domain": self.domain,
                "partition": partition,
                "fields": risky_fields,
                "score": round(
                    result.score,
                    4
                ),
                "k": result.k,
                "uniqueness": round(
                    result.uniqueness,
                    4
                ),
                "sample_size": result.sample_size,
                "window_size": len(records),
            }

            # ----------------------------------------------------------------
            # Publish risk event
            # ----------------------------------------------------------------

            await self.risk_producer.send_and_wait(
                self.risk_topic,
                value=event
            )

            # ----------------------------------------------------------------
            # EthiMask
            # ----------------------------------------------------------------

            masked_results = []

            if ethimask_requests:

                try:

                    masked_results = (
                        await self.ethimask_client.mask_batch(
                            requests=ethimask_requests,
                            role="labeler",
                            context="streamshield",
                            purpose="risk_mitigation",
                        )
                    )

                    logger.info(
                        "ETHIMASK BATCH TERMINE | partition=%s | "
                        "fields=%s | demandes=%s | résultats=%s",
                        partition,
                        risky_fields,
                        len(ethimask_requests),
                        len(masked_results),
                    )

                except Exception as exc:

                    logger.error(
                        "ETHIMASK ERROR | partition=%s | "
                        "fields=%s | error=%s",
                        partition,
                        risky_fields,
                        exc
                    )

            # ----------------------------------------------------------------
            # MongoDB
            # ----------------------------------------------------------------

            if db is not None:

                await db.streamshield_risk_events.insert_one({
                    **event,
                    "processing_timestamp": time.time(),
                    "kafka_timestamp_ms": latest_kafka_ts,
                })

            logger.warning(
                "RISK DETECTED fields=%s score=%.3f "
                "k=%s partition=%s -> publié sur '%s'",
                result.fields,
                result.score,
                result.k,
                partition,
                self.risk_topic
            )

    # ========================================================================
    # MAIN RUN LOOP
    # ========================================================================

    async def run(self):

        await self.start()

        try:

            while not self._stopping.is_set():

                try:

                    result = await self.consumer.getmany(
                        timeout_ms=1000,
                        max_records=500
                    )

                    for tp, messages in result.items():

                        for msg in messages:

                            if msg.value is None:

                                logger.error(
                                    "MESSAGE IGNORE | "
                                    "topic=%s | partition=%s | offset=%s",
                                    tp.topic,
                                    tp.partition,
                                    msg.offset
                                )

                                continue

                            # ------------------------------------------------
                            # Traitement complet
                            # ------------------------------------------------

                            await self.process_record(
                                msg.value,
                                tp.partition,
                                msg.offset,
                                msg.timestamp
                            )

                            # ------------------------------------------------
                            # Counter Prometheus
                            # ------------------------------------------------

                            kafka_messages_processed.labels(
                                topic=tp.topic
                            ).inc()

                        # ----------------------------------------------------
                        # Commit manuel APRÈS traitement
                        # ----------------------------------------------------

                        if messages:

                            await self.consumer.commit({
                                tp: messages[-1].offset + 1
                            })

                            # ------------------------------------------------
                            # Mise à jour du lag
                            # ------------------------------------------------

                            await self.update_consumer_lag()

                except KafkaConnectionError as exc:

                    logger.warning(
                        "Connexion Kafka perdue (%s) "
                        "-- nouvelle tentative dans 5s",
                        exc
                    )

                    await asyncio.sleep(5)

                except Exception as exc:

                    logger.exception(
                        "Erreur inattendue dans la boucle consumer: %s",
                        exc
                    )

                    await asyncio.sleep(2)

        finally:

            await self.stop()


# ============================================================================
# CLI
# ============================================================================

async def main():

    parser = argparse.ArgumentParser(
        description="StreamShield Kafka Consumer"
    )

    parser.add_argument(
        "--domain",
        default="clients",
        help="Domaine Kafka à consommer"
    )

    args = parser.parse_args()

    consumer = StreamShieldConsumer(
        domain=args.domain
    )

    loop = asyncio.get_running_loop()

    def handle_signal():

        logger.info(
            "Signal d'arrêt reçu..."
        )

        consumer._stopping.set()

    for sig in (
        signal.SIGINT,
        signal.SIGTERM
    ):

        try:
            loop.add_signal_handler(
                sig,
                handle_signal
            )
        except NotImplementedError:
            # Windows
            pass

    await consumer.run()


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Arrêt demandé (Ctrl+C)"
        )
