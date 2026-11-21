from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.main import app
from app.migrate import discover
from app.types import Money


async def test_health_without_db():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_money_is_a_number_in_json():
    class Line(BaseModel):
        price: Money

    assert Line(price=Decimal("74.99")).model_dump_json() == '{"price":74.99}'


def test_catalog_migrations_come_first():
    versions = [version for version, _ in discover()]
    assert versions[0] == "catalog/001_init.sql"
