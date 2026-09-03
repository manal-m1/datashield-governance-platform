import logging
import os
from typing import Dict, Any

import requests

logger = logging.getLogger("streamshield.cleaning_client")


class CleaningClient:

    def __init__(self):
        self.base_url = os.getenv(
            "CLEANING_SERVICE_URL",
            "http://cleaning-serv:8004"
        ).rstrip("/")

        self.timeout = int(
            os.getenv("CLEANING_TIMEOUT", "10")
        )

    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Récupère le dataset nettoyé depuis Cleaning Service.
        """

        url = (
            f"{self.base_url}"
            f"/cleaning/datasets/{dataset_id}/full-scan-data"
        )

        logger.info(
            f"Récupération du dataset {dataset_id} "
            f"depuis Cleaning Service"
        )

        try:
            response = requests.get(
                url,
                timeout=self.timeout
            )

            response.raise_for_status()

            data = response.json()

            logger.info(
                f"Dataset {dataset_id} récupéré depuis Cleaning"
            )

            return data

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Erreur Cleaning Service pour "
                f"{dataset_id}: {e}"
            )
            raise