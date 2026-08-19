"""
StreamShield - Tâche 2, étape 1
Fenêtre glissante (sliding window) par partition.

Garde en mémoire les enregistrements des N dernières secondes, pour que le
calcul de risque (Tâche 2.3+) porte sur "ce qui se passe maintenant", pas sur
tout l'historique du topic. Une fenêtre par clé de partition -- cohérent avec
le partitionnement Kafka décrit en section 2.3 du cahier des charges (les
événements d'une même entité/ville atterrissent sur la même partition).
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List


@dataclass
class WindowedRecord:
    """Un enregistrement horodaté, tel qu'il vit dans la fenêtre."""
    timestamp: float
    data: Dict[str, Any]


class SlidingWindow:
    """
    Fenêtre glissante pour UNE partition.

    size_seconds : durée de la fenêtre (60s par défaut, cf. section 2.4)
    slide_seconds : n'est pas géré ici comme un déclenchement actif -- la
        purge se fait paresseusement à chaque add()/get_records(), ce qui
        revient au même résultat pour du calcul de risque à la demande,
        sans avoir besoin d'un thread de purge séparé.
    """

    def __init__(self, size_seconds: int = 60):
        self.size_seconds = size_seconds
        self._buffer: Deque[WindowedRecord] = deque()

    def add(self, record: Dict[str, Any], timestamp: float = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._buffer.append(WindowedRecord(timestamp=ts, data=record))
        self._evict_expired()

    def _evict_expired(self) -> None:
        cutoff = time.time() - self.size_seconds
        while self._buffer and self._buffer[0].timestamp < cutoff:
            self._buffer.popleft()

    def get_records(self) -> List[Dict[str, Any]]:
        """Retourne les enregistrements actuellement dans la fenêtre (purge d'abord)."""
        self._evict_expired()
        return [r.data for r in self._buffer]

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._buffer)


class PartitionedSlidingWindow:
    """
    Gère une SlidingWindow indépendante par clé de partition Kafka.
    C'est l'objet que le consumer manipule directement : une entrée par
    partition, jamais de mélange entre partitions différentes.
    """

    def __init__(self, size_seconds: int = 60):
        self.size_seconds = size_seconds
        self._windows: Dict[int, SlidingWindow] = {}

    def _get_or_create(self, partition: int) -> SlidingWindow:
        if partition not in self._windows:
            self._windows[partition] = SlidingWindow(self.size_seconds)
        return self._windows[partition]

    def add(self, partition: int, record: Dict[str, Any], timestamp: float = None) -> None:
        self._get_or_create(partition).add(record, timestamp)

    def get_records(self, partition: int) -> List[Dict[str, Any]]:
        return self._get_or_create(partition).get_records()

    def window_size(self, partition: int) -> int:
        return len(self._get_or_create(partition))