import logging
import time
from typing import List, Dict, Any

from backend.database.mongodb import fuzzy_rules_collection

logger = logging.getLogger("streamshield.fuzzy_rule_repository")

CACHE_TTL_SECONDS = 300

_rules_cache: List[Dict[str, Any]] | None = None
_rules_cache_timestamp: float = 0.0


async def load_fuzzy_rules(
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:

    global _rules_cache
    global _rules_cache_timestamp

    now = time.monotonic()

    if (
        not force_refresh
        and _rules_cache is not None
        and (now - _rules_cache_timestamp)
        < CACHE_TTL_SECONDS
    ):
        logger.debug(
            "Règles fuzzy récupérées depuis le cache "
            f"(TTL={CACHE_TTL_SECONDS}s)"
        )
        return _rules_cache

    logger.info(
        "Chargement des règles fuzzy depuis MongoDB"
    )

    cursor = fuzzy_rules_collection.find(
        {"enabled": True}
    ).sort(
        "priority",
        1,
    )

    rules = await cursor.to_list(
        length=None
    )

    for rule in rules:
        if "_id" in rule:
            rule["_id"] = str(rule["_id"])

    _rules_cache = rules
    _rules_cache_timestamp = now

    logger.info(
        f"{len(rules)} règles fuzzy chargées depuis MongoDB "
        f"et mises en cache pour {CACHE_TTL_SECONDS}s"
    )

    return rules
