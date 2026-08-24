"""
StreamShield - Tâche 2, étape 1 (v2 - corrigée après revue)
"""
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List

logger = logging.getLogger("streamshield.sliding_window")


@dataclass
class WindowedRecord:
    timestamp: float
    data: Dict[str, Any]


class SlidingWindow:
    def __init__(self, size_seconds: int = 60, max_size: int = 50_000):
        self.size_seconds = size_seconds
        self.max_size = max_size
        self._buffer: Deque[WindowedRecord] = deque()
        self._evicted_for_capacity = 0

    def add(self, record: Dict[str, Any], timestamp: float = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._buffer.append(WindowedRecord(timestamp=ts, data=record))
        self._evict_expired()
        self._evict_over_capacity()

    def _evict_expired(self) -> None:
        cutoff = time.time() - self.size_seconds
        while self._buffer and self._buffer[0].timestamp < cutoff:
            self._buffer.popleft()

    def _evict_over_capacity(self) -> None:
        if len(self._buffer) <= self.max_size:
            return
        overflow = len(self._buffer) - self.max_size
        for _ in range(overflow):
            self._buffer.popleft()
        self._evicted_for_capacity += overflow
        logger.warning(
            f"Fenêtre au plafond mémoire (max_size={self.max_size}) -- "
            f"{overflow} enregistrement(s) évincé(s) prématurément."
        )

    def get_records(self) -> List[Dict[str, Any]]:
        self._evict_expired()
        return [r.data for r in self._buffer]

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._buffer)

    @property
    def is_at_capacity(self) -> bool:
        return len(self._buffer) >= self.max_size


class PartitionedSlidingWindow:
    def __init__(self, size_seconds: int = 60, max_size: int = 50_000):
        self.size_seconds = size_seconds
        self.max_size = max_size
        self._windows: Dict[int, SlidingWindow] = {}

    def _get_or_create(self, partition: int) -> SlidingWindow:
        if partition not in self._windows:
            self._windows[partition] = SlidingWindow(self.size_seconds, self.max_size)
        return self._windows[partition]

    def add(self, partition: int, record: Dict[str, Any], timestamp: float = None) -> None:
        self._get_or_create(partition).add(record, timestamp)

    def get_records(self, partition: int) -> List[Dict[str, Any]]:
        return self._get_or_create(partition).get_records()

    def window_size(self, partition: int) -> int:
        return len(self._get_or_create(partition))

    def any_at_capacity(self) -> bool:
        return any(w.is_at_capacity for w in self._windows.values())