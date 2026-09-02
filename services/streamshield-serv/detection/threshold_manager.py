"""
StreamShield - Gestion des seuils de risque par domaine (livrable Tâche 2 :
"Jeu de règles de seuils configurables, persisté dans MongoDB").

Chaque domaine métier (clients, rh, sante...) peut avoir son propre seuil de
déclenchement d'alerte -- cohérent avec la user story administrateur :
"je veux ajuster le seuil de risque pour l'adapter au niveau de sensibilité
de chaque domaine métier".
"""
from typing import Optional

DEFAULT_THRESHOLD = 0.70


class ThresholdManager:
    def __init__(self, db):
        self.collection = db.streamshield_thresholds if db is not None else None
        self._cache: dict[str, float] = {}

    async def get_threshold(self, domain: str) -> float:
        """Retourne le seuil configuré pour ce domaine, ou la valeur par défaut."""
        if domain in self._cache:
            return self._cache[domain]

        if self.collection is not None:
            doc = await self.collection.find_one({"_id": domain})
            if doc:
                self._cache[domain] = doc["threshold"]
                return doc["threshold"]

        return DEFAULT_THRESHOLD

    async def set_threshold(self, domain: str, threshold: float) -> None:
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("Le seuil doit être compris entre 0.0 et 1.0")

        self._cache[domain] = threshold
        if self.collection is not None:
            await self.collection.update_one(
                {"_id": domain},
                {"$set": {"threshold": threshold}},
                upsert=True,
            )

    async def list_all(self) -> dict:
        if self.collection is None:
            return {}
        result = {}
        async for doc in self.collection.find():
            result[doc["_id"]] = doc["threshold"]
        return result