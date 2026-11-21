"""Ввічливий HTTP-клієнт для неофіційних API: обмеження паралельності, пауза між запитами, повтори.

На 429 (Too Many Requests) клієнт ставить на паузу всі запити, а не лише той, що отримав відмову:
інакше решта паралельних запитів продовжує бити в ліміт. Zakaz.ua вмикає ліміт приблизно на 2 хвилини,
якщо швидко пройтися пошуком по кількох магазинах.
"""

import asyncio
import logging

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_S = 60.0


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    try:
        return min(float(value), MAX_RETRY_AFTER_S) if value else None
    except ValueError:  # формат HTTP-date: ігноруємо, вистачить власного backoff
        return None


class Http:
    def __init__(
        self,
        concurrency: int = 5,
        delay: float = 0.2,
        retries: int = 5,
        timeout: float = 25.0,
        backoff: float = 2.0,
    ):
        # Нейтральний User-Agent: без назви проєкту й особистих даних.
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        self._sem = asyncio.Semaphore(concurrency)
        self._delay = delay
        self._retries = retries
        self._backoff = backoff
        self._resume_at = 0.0  # спільна пауза після 429 (час event loop)
        self.requests = 0
        self.failures = 0
        self.rate_limited = 0

    async def _wait_for_cooldown(self) -> None:
        pause = self._resume_at - asyncio.get_running_loop().time()
        if pause > 0:  # якщо за цей час прийде новий 429, наступний запит знову почекає
            await asyncio.sleep(pause)

    async def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        loop = asyncio.get_running_loop()
        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            wait = self._backoff * 2 ** (attempt - 1)  # 2, 4, 8, 16 с
            await self._wait_for_cooldown()
            async with self._sem:
                try:
                    response = await self._client.get(url, params=params, headers=headers)
                    self.requests += 1
                    if response.status_code in RETRY_STATUSES:
                        if response.status_code == 429:
                            self.rate_limited += 1
                            wait = max(wait * 2.5, _retry_after(response) or 0.0)  # 5, 10, 20, 40 с
                            self._resume_at = max(self._resume_at, loop.time() + wait)
                        raise httpx.HTTPStatusError(
                            f"retryable status {response.status_code}", request=response.request, response=response
                        )
                    response.raise_for_status()
                    await asyncio.sleep(self._delay)
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code not in RETRY_STATUSES:
                        self.failures += 1
                        raise
                    last_error = exc
                except httpx.TransportError as exc:
                    last_error = exc
            if attempt < self._retries:
                await asyncio.sleep(wait)
        self.failures += 1
        log.warning("giving up on %s: %r", url, last_error)
        assert last_error is not None
        raise last_error

    async def aclose(self) -> None:
        await self._client.aclose()
