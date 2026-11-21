"""Простий in-memory ліміт запитів на IP (ковзне вікно).

Захищає платні виклики Groq від зловживань у демо. На Vercel пам'ять окрема для кожного інстансу
функції, тож це «м'який» ліміт; для продакшну — Redis/Upstash або ліміт на рівні шлюзу.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from backend.voice.errors import VoiceError

VOICE_LIMIT = 10        # запитів
VOICE_WINDOW_S = 60.0   # за хвилину


class RateLimiter:
    def __init__(self, limit: int, window_s: float):
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


voice_limiter = RateLimiter(VOICE_LIMIT, VOICE_WINDOW_S)


def client_ip(request: Request) -> str:
    # Vercel ставить справжній IP клієнта першим у X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_voice_limit(request: Request) -> None:
    if not voice_limiter.allow(client_ip(request)):
        raise VoiceError("rate_limited", "Забагато запитів. Спробуйте за хвилину", status=429, fallback=False)
