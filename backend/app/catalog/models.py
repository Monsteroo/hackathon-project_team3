"""ORM-моделі модуля catalog. Дзеркало migrations/*.sql: схему змінюй міграцією, а потім тут."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Identity, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    chain: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    has_pickup: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    gtin: Mapped[str | None] = mapped_column(Text, unique=True)
    source_key: Mapped[str | None] = mapped_column(Text, unique=True)
    alt_gtins: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    title: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    pack_qty: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    pack_unit: Mapped[str | None] = mapped_column(Text)
    fat_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ingredients: Mapped[str | None] = mapped_column(Text)
    composition_known: Mapped[bool] = mapped_column(default=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    nutrition: Mapped[dict | None] = mapped_column(JSONB)
    img_url: Mapped[str | None] = mapped_column(Text)
    search_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Offer(Base):
    __tablename__ = "offers"

    store_id: Mapped[str] = mapped_column(Text, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    source_sku: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    title_raw: Mapped[str] = mapped_column(Text)
    source_category: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    promo_percent: Mapped[int | None] = mapped_column(SmallInteger)
    promo_until: Mapped[date | None]
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(default=True)
    stock: Mapped[int | None]
    url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())


class EtlRun(Base):
    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text, default="manual")
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
