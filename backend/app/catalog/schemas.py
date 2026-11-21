"""Контракт модуля catalog з рештою команди (UI, агент, геолокація).

Поля можна додавати. Перейменування чи видалення — лише після домовленості з командою.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.types import Money


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    store_id: str = Field(validation_alias="id", description='Zakaz store id ("482010105") або branchId Сільпо')
    source: str = Field(description="zakaz | silpo")
    chain: str = Field(description="silpo, novus, auchan, metro, ultramarket, ekomarket, ...")
    name: str
    city: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    has_pickup: bool = False
    offers_count: int = Field(default=0, description="скільки товарів у наявності з цінами є в БД для магазину")


class PriceOut(BaseModel):
    """Ціна товару в одному магазині."""

    store_id: str
    chain: str
    store_name: str
    city: str | None = None
    address: str | None = None
    price: Money = Field(description="грн за пачку; для вагових товарів — за кг")
    old_price: Money | None = Field(default=None, description="ціна до знижки, якщо діє акція")
    promo_percent: int | None = None
    promo_until: date | None = None
    unit_price: Money | None = Field(default=None, description="грн за кг / л / шт: для чесного порівняння пачок")
    unit_price_label: str = Field(description="₴/кг | ₴/л | ₴/шт")
    in_stock: bool
    stock: int | None = Field(default=None, description="залишок, лише Сільпо")
    url: str | None = None
    fetched_at: datetime


class ProductPricesOut(BaseModel):
    """Один товар (той самий GTIN у різних мережах) і його ціни в запитаних магазинах."""

    product_id: int
    gtin: str | None = None
    title: str
    brand: str | None = None
    category: str | None = Field(default=None, description="канонічна категорія: milk, curd, eggs, ...")
    pack_qty: float | None = Field(default=None, description="вага/об'єм/кількість пачки, напр. 950")
    pack_unit: str | None = Field(default=None, description="g | ml | pcs")
    fat_pct: float | None = None
    tags: list[str] = Field(default_factory=list, description="sugar, palm_oil, lactose, private_label")
    composition_known: bool = Field(default=False, description="false = склад невідомий (не те саме, що «чистий»)")
    img_url: str | None = None
    stores_count: int
    min_price: Money
    max_price: Money
    min_unit_price: Money | None = None
    prices: list[PriceOut] = Field(description="від найдешевшої")


class PriceSearchOut(BaseModel):
    query: str
    tokens: list[str] = Field(description="слова запиту після нормалізації; товар має містити кожне")
    store_ids: list[str]
    missing_store_ids: list[str] = Field(description="запитані store_id, яких немає в БД")
    products: list[ProductPricesOut] = Field(description="від найрелевантнішого")


class EtlRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger: str = Field(description="schedule | manual")
    status: str = Field(description="running | ok | failed")
    started_at: datetime
    finished_at: datetime | None = None
    stats: dict
    error: str | None = None


class EtlStatusOut(BaseModel):
    schedule: str = Field(description='crontab, напр. "0 3 * * *"')
    timezone: str
    scheduler_running: bool
    next_run_at: datetime | None = Field(description="коли наступний нічний запуск (якщо планувальник працює)")
    prices_updated_at: datetime | None = Field(description="кінець останнього успішного запуску; показуйте в UI")
    last_runs: list[EtlRunOut]
