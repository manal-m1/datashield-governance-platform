import logging
import time
from typing import Dict

from backend.database.mongodb import field_sensitivity_collection

logger = logging.getLogger(
    "streamshield.field_sensitivity_repository"
)

# ============================================================================
# Configuration
# ============================================================================

CACHE_TTL_SECONDS = 300  # 5 minutes
DEFAULT_SENSITIVITY = "medium"

# ============================================================================
# Cache mémoire
# ============================================================================

_field_sensitivity_cache: Dict[str, str] | None = None
_field_sensitivity_cache_timestamp: float = 0.0


async def load_field_sensitivity(
    force_refresh: bool = False,
) -> Dict[str, str]:
    """
    Charge les sensibilités des champs depuis MongoDB.

    MongoDB :
        field       -> nom du champ
        sensitivity -> low / medium / high / critical
        context     -> contexte métier

    Un cache TTL est utilisé afin de limiter les accès à MongoDB.
    """

    global _field_sensitivity_cache
    global _field_sensitivity_cache_timestamp

    now = time.monotonic()

    # ------------------------------------------------------------------------
    # 1. Cache valide
    # ------------------------------------------------------------------------

    if (
        not force_refresh
        and _field_sensitivity_cache is not None
        and (
            now - _field_sensitivity_cache_timestamp
        ) < CACHE_TTL_SECONDS
    ):
        logger.debug(
            "Field sensitivity récupérée depuis le cache "
            f"(TTL={CACHE_TTL_SECONDS}s)"
        )

        return _field_sensitivity_cache

    # ------------------------------------------------------------------------
    # 2. Chargement MongoDB
    # ------------------------------------------------------------------------

    logger.info(
        "Chargement des sensibilités depuis MongoDB"
    )

    cursor = field_sensitivity_collection.find(
        {},
        {
            "_id": 0,
            "field": 1,
            "sensitivity": 1,
            "context": 1,
        },
    )

    documents = await cursor.to_list(
        length=None
    )

    field_sensitivity: Dict[str, str] = {}

    for document in documents:

        field = document.get("field")

        if not field:
            logger.warning(
                "Document de sensibilité ignoré : "
                "champ 'field' manquant."
            )
            continue

        sensitivity = document.get(
            "sensitivity",
            DEFAULT_SENSITIVITY,
        )

        field_sensitivity[field] = sensitivity

    # ------------------------------------------------------------------------
    # 3. Mise à jour du cache
    # ------------------------------------------------------------------------

    _field_sensitivity_cache = field_sensitivity
    _field_sensitivity_cache_timestamp = now

    logger.info(
        f"{len(field_sensitivity)} sensibilités chargées "
        "depuis MongoDB et mises en cache pour "
        f"{CACHE_TTL_SECONDS}s"
    )

    return field_sensitivity
