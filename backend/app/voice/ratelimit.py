"""Простий in-memory ліміт запитів на IP (ковзне вікно) для /voice/*.

Ключ X-API-Key у бандлі фронту не секретний, тож платні виклики Groq захищає саме цей ліміт.
Пам'ять окрема для кожного процесу uvicorn/serverless-інстансу — це «м'який» ліміт;
для продакшну — Redis/Upstash або ліміт на рівні шлюзу.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import get_settings
from app.voice.errors import VoiceError

WINDOW_S = 60.0


class RateLimiter:
    def __init__(self, window_s: float = WINDOW_S):
        self.window_s = window_s
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


voice_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # За проксі (Vercel, nginx) справжній IP клієнта перший у X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_voice_limit(request: Request) -> None:
    if not voice_limiter.allow(client_ip(request), get_settings().voice_rate_limit_per_min):
        raise VoiceError("rate_limited", "too many requests, retry in a minute", status=429, fallback=False)
