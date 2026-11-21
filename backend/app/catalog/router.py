from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.catalog import service
from app.catalog.schemas import EtlStatusOut, PriceSearchOut, StoreOut
from app.db import SessionDep

router = APIRouter(prefix="/catalog", tags=["catalog"])

MAX_STORE_IDS = 300


def _split(values: list[str] | None) -> list[str]:
    """Приймаємо і ?store_ids=a&store_ids=b, і ?store_ids=a,b: фронту й агенту зручно по-різному."""
    return [part.strip() for value in values or [] for part in value.split(",") if part.strip()]


@router.get("/stores", response_model=list[StoreOut])
async def list_stores(
    session: SessionDep,
    city: Annotated[str | None, Query(description='Українською, напр. "Київ"')] = None,
    chain: Annotated[str | None, Query(description="silpo, novus, auchan, ...")] = None,
    with_prices: Annotated[bool, Query(description="лише магазини, для яких у БД є ціни")] = True,
) -> list[StoreOut]:
    """Доступні магазини з координатами. Їхні store_id передавайте в /catalog/prices."""
    return await service.list_stores(session, city=city, chain=chain, with_prices=with_prices)


@router.get("/prices", response_model=PriceSearchOut)
async def search_prices(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=200, description='Назва товару, напр. "молоко галичина 2,5"')],
    store_ids: Annotated[
        list[str] | None,
        Query(description="store_id з /catalog/stores: повторюваний параметр або через кому. Без нього — усі магазини"),
    ] = None,
    category: Annotated[
        str | None, Query(description="канонічна категорія: milk, curd, eggs, coffee_ground, ...")
    ] = None,
    exclude: Annotated[
        list[str] | None,
        Query(description="відсіяти теги: sugar, palm_oil, lactose (товари з невідомим складом теж відсіюються)"),
    ] = None,
    in_stock_only: Annotated[bool, Query(description="лише товари в наявності")] = True,
    limit: Annotated[int, Query(ge=1, le=100, description="скільки товарів повернути")] = 20,
) -> PriceSearchOut:
    """Ціни товару за назвою в масиві магазинів: товари від найрелевантнішого, ціни в кожному — від найдешевшої."""
    ids = _split(store_ids)
    if len(ids) > MAX_STORE_IDS:
        raise HTTPException(status_code=422, detail=f"too many store_ids (max {MAX_STORE_IDS})")
    try:
        return await service.search_prices(
            session,
            query=q,
            store_ids=ids,
            category=category,
            exclude=_split(exclude),
            in_stock_only=in_stock_only,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/etl/status", response_model=EtlStatusOut)
async def etl_status(session: SessionDep) -> EtlStatusOut:
    """Розклад нічного ETL, наступний запуск і журнал останніх запусків."""
    return await service.etl_status(session)
