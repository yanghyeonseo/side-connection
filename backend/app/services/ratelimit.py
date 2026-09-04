"""간단한 IP별 슬라이딩 윈도 요청 제한.

사례번호는 8자리 능력 토큰이라 무차별 대입을 느리게 만드는 것이 목적이다.
단일 프로세스 메모리 기준이며, 다중 인스턴스로 확장하면 Redis 등으로 옮긴다.
"""

import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:
                self._evict_stale_locked(now)
            return True

    def _evict_stale_locked(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > self._window]
        for key in stale:
            del self._hits[key]
