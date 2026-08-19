"""
StreamShield - point d'entrée unique du service
Lance dans le même process asyncio :
  - le consumer Kafka (consumer/main.py -> StreamShieldConsumer)
  - l'API FastAPI (api/main.py -> app)
"""
import asyncio
import logging
import os
import signal

import uvicorn

from consumer.main import StreamShieldConsumer, CONSUMER_GROUP_ID
from api.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("streamshield.main")

DOMAIN = os.getenv("STREAMSHIELD_DOMAIN", "clients")
API_PORT = int(os.getenv("STREAMSHIELD_API_PORT", "8010"))
WINDOW_SECONDS = int(os.getenv("STREAMSHIELD_WINDOW_SECONDS", "60"))
DETECTION_INTERVAL = int(os.getenv("STREAMSHIELD_DETECTION_INTERVAL", "50"))


async def run_api():
    config = uvicorn.Config(app, host="0.0.0.0", port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    logger.info(f"Démarrage StreamShield unifié — domaine={DOMAIN}, API sur port {API_PORT}")

    consumer = StreamShieldConsumer(
        domain=DOMAIN,
        group_id=CONSUMER_GROUP_ID,
        window_seconds=WINDOW_SECONDS,
        detection_interval=DETECTION_INTERVAL,
    )

    loop = asyncio.get_running_loop()

    def _handle_signal():
        logger.info("Signal d'arrêt reçu, fermeture en cours...")
        consumer._stopping.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    tasks = [
        asyncio.create_task(consumer.run(), name="consumer"),
        asyncio.create_task(run_api(), name="api"),
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # si l'API tombe alors que le consumer tourne encore (ou l'inverse),
    # on arrête l'autre plutôt que de laisser le conteneur à moitié mort
    for task in pending:
        task.cancel()

    for task in done:
        exc = task.exception()
        if exc:
            logger.error(f"Tâche '{task.get_name()}' a échoué: {exc}")
            raise exc


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt demandé (Ctrl+C)")