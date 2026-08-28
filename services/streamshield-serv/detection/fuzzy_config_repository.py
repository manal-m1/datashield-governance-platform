import logging
import time
from typing import Dict, Any

from backend.database.mongodb import fuzzy_config_collection

logger = logging.getLogger("streamshield.fuzzy_config_repository")

CACHE_TTL_SECONDS = 300

_config_cache: Dict[str, Any] | None = None
_config_cache_timestamp: float = 0.0


async def load_fuzzy_config(
    force_refresh: bool = False,
) -> Dict[str, Any]:

    global _config_cache
    global _config_cache_timestamp

    now = time.monotonic()

    if (
        not force_refresh
        and _config_cache is not None
        and (now - _config_cache_timestamp)
        < CACHE_TTL_SECONDS
    ):
        logger.debug(
            f"Fuzzy config récupérée depuis le cache "
            f"(TTL={CACHE_TTL_SECONDS}s)"
        )
        return _config_cache

    logger.info(
        "Chargement de la configuration fuzzy depuis MongoDB"
    )

    config = await fuzzy_config_collection.find_one(
        {"enabled": True}
    )

    if config is None:
        raise RuntimeError(
            "Aucune configuration fuzzy active trouvée "
            "dans streamshield_fuzzy_config"
        )

    config.pop("_id", None)

    _config_cache = config
    _config_cache_timestamp = now

    logger.info(
        "Configuration fuzzy chargée depuis MongoDB "
        f"et mise en cache pour {CACHE_TTL_SECONDS}s"
    )

    return config
