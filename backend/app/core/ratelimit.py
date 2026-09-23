"""Простой in-memory rate limiter для login endpoint.

Ограничивает число неудачных попыток входа по IP и по username.
Для single-instance приложения достаточно; для нескольких инстансов
требуется внешнее хранилище (Redis и т.п.).
"""

import threading
import time
from collections import defaultdict
from typing import Optional


class LoginRateLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 900) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        timestamps = self._failures.get(key)
        if not timestamps:
            return
        kept = [t for t in timestamps if now - t < self.window_seconds]
        if kept:
            self._failures[key] = kept
        else:
            self._failures.pop(key, None)

    def is_blocked(self, key: str, now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            self._prune(key, now)
            return len(self._failures.get(key, [])) >= self.max_failures

    def record_failure(self, key: str, now: Optional[float] = None) -> None:
        now = now or time.time()
        with self._lock:
            self._failures[key].append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()