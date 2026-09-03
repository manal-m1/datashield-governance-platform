"""
Client HTTP asynchrone pour communiquer avec EthiMask.

StreamShield est responsable de la détection du risque.
EthiMask est responsable du masquage effectif des données.
"""

import os
import logging
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger("streamshield.ethimask_client")


class EthiMaskClient:
    """
    Client permettant à StreamShield d'appeler le service EthiMask.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = (
            base_url
            or os.getenv(
                "ETHIMASK_SERVICE_URL",
                "http://ethimask-service:8009",
            )
        ).rstrip("/")

        self.timeout = timeout

    async def health_check(self) -> bool:
        """
        Vérifie que le service EthiMask est disponible.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/health"
                )

                response.raise_for_status()

                data = response.json()

                return data.get("status") == "healthy"

        except Exception as exc:
            logger.error(
                "EthiMask indisponible : %s",
                exc,
            )
            return False

    async def mask(
        self,
        data: Dict[str, Any],
        detections: List[Dict[str, Any]],
        role: str = "labeler",
        context: str = "streamshield",
        purpose: str = "risk_mitigation",
        history_stats: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Envoie une demande de masquage à EthiMask.

        Parameters
        ----------
        data:
            Données contenant les champs à protéger.

        detections:
            Liste des champs détectés comme sensibles.

        role:
            Rôle utilisateur transmis à EthiMask.

        context:
            Contexte de traitement.

        purpose:
            Finalité du masquage.

        history_stats:
            Statistiques historiques facultatives.
        """

        if history_stats is None:
            history_stats = {
                "conformity": 0.8,
                "frequency": 0.5,
                "violations": 0.0,
            }

        payload = {
            "data": data,
            "detections": detections,
            "config": {
                "role": role,
                "context": context,
                "purpose": purpose,
                "history_stats": history_stats,
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    f"{self.base_url}/mask",
                    json=payload,
                )

                response.raise_for_status()

                result = response.json()

                logger.info(
                    "Masquage EthiMask réussi : "
                    "%s champ(s) traité(s)",
                    result.get("masking_applied", 0),
                )

                return result

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erreur HTTP EthiMask : status=%s body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise

        except httpx.RequestError as exc:
            logger.error(
                "Impossible de contacter EthiMask : %s",
                exc,
            )
            raise
    async def mask_batch(
        self,
        requests: List[Dict[str, Any]],
        role: str = "labeler",
        context: str = "streamshield",
        purpose: str = "risk_mitigation",
        history_stats: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Envoie plusieurs demandes de masquage à EthiMask
        en une seule requête HTTP vers /mask/batch.
        """

        if history_stats is None:
            history_stats = {
                "conformity": 0.8,
                "frequency": 0.5,
                "violations": 0.0,
            }

        batch_requests = []

        for item in requests:
            batch_requests.append({
                "data": item["data"],
                "detections": item["detections"],
                "config": {
                    "role": role,
                    "context": context,
                    "purpose": purpose,
                    "history_stats": history_stats,
                },
            })

        if not batch_requests:
            return []

        payload = {
            "requests": batch_requests
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    f"{self.base_url}/mask/batch",
                    json=payload,
                )

                response.raise_for_status()

                result = response.json()

                results = result.get("results", [])

                logger.info(
                    "Batch EthiMask réussi : "
                    "%s demande(s) traitée(s)",
                    len(results),
                )

                return results

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erreur HTTP EthiMask batch : "
                "status=%s body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise

        except httpx.RequestError as exc:
            logger.error(
                "Impossible de contacter EthiMask batch : %s",
                exc,
            )
            raise