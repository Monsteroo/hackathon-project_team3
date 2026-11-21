import pytest

from app.voice.ratelimit import voice_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    voice_limiter.reset()
    yield
    voice_limiter.reset()
