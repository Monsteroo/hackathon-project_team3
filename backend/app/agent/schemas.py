"""Контракт модуля agent з фронтом (Учасник 3) і евалами (Учасник 4).

Поля можна додавати. Перейменування чи видалення — лише після домовленості з командою й оновлення mocks/.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.types import Money

Chain = Literal["silpo", "novus", "auchan", "metro", "ultramarket", "ekomarket", "megamarket", "tavriav"]
Category = Literal[
    "milk", "kefir", "curd", "sour_cream", "butter", "cheese", "eggs", "flour", "sugar", "vanilla_sugar",
    "buckwheat", "rice", "pasta", "sunflower_oil", "bread", "coffee_ground", "coffee_beans", "tea", "bananas", "apples",
]  # fmt: skip
ExcludeTag = Literal["sugar", "palm_oil", "lactose"]
Unit = Literal["g", "ml", "pcs"]
TravelMode = Literal["walk", "car"]


# ---------- Результат розбору запиту (це й JSON-схема для LLM) ----------
class RequestedItem(BaseModel):
    name: str = Field(description="Коротка назва українською для UI, напр. «сир кисломолочний»")
    search_query: str = Field(description="Слова для пошуку в назві товару в каталозі, напр. «сир кисломолочний»")
    category: Category | None = Field(None, description="Канонічна категорія каталогу, якщо товар до неї належить")
    quantity: float = Field(description="Скільки потрібно в unit")
    unit: Unit
    brand: str | None = Field(None, description="Лише якщо користувач сам назвав бренд")
    optional: bool = Field(False, description="Можна прибрати, якщо не вкладаємося в бюджет")
    gtin: str | None = Field(None, description="Не заповнюй. Лише для товару, вибраного з каталогу на екрані 2")
    exclude: list[str] = Field(default_factory=list, description="Не заповнюй. Фільтри складу цієї позиції з екрана 2")


class Constraints(BaseModel):
    budget_uah: float | None = None
    exclude: list[ExcludeTag] = Field(default_factory=list, description="Теги складу, яких не має бути")
    travel_mode: TravelMode = "walk"
    radius_km: float | None = Field(None, description="None → радіус за замовчуванням для travel_mode")
    preferred_chains: list[Chain] = Field(default_factory=list)


class ParsedRequest(BaseModel):
    items: list[RequestedItem]
    constraints: Constraints = Field(default_factory=Constraints)
    servings: int | None = None


# ---------- Вхід ендпоінтів ----------
class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="Розпізнаний або введений текст запиту")


class AgentItem(BaseModel):
    """Позиція кошика з екрана 2 (контракт «Позиція кошика» в CLAUDE.md) + назва для показу."""

    label: str | None = Field(None, max_length=200, description="Назва для людини / назва товару з каталогу")
    category: Category | None = None
    gtin: str | None = None
    query: str | None = Field(None, max_length=200)
    need: float = Field(gt=0, description="Скільки потрібно в unit")
    unit: Unit
    exclude: list[str] = Field(default_factory=list, description="sugar, palm_oil, lactose, private_label")


class BasketIn(BaseModel):
    """Або text (агент розбирає сам), або items — уже підтверджений список з екрана 2 (без виклику LLM).

    text, raw_text, mode, radius_km — рівно ті поля, що повертає /voice/transcribe.
    """

    text: str = Field("", max_length=1000, description="Розпізнаний або введений текст запиту")
    items: list[AgentItem] | None = Field(None, max_length=50, description="Відредагований список з екрана 2")
    budget_uah: float | None = Field(None, gt=0, description="Бюджет з екрана 2 (для items)")
    raw_text: str | None = Field(None, description="Сира розшифровка STT — для логів і евалів")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    mode: TravelMode | None = Field(None, description="З VoiceResult або перемикача в UI; головніше за розбір тексту")
    radius_km: float | None = Field(None, gt=0, le=50, description="З VoiceResult; None — дефолт модуля geo")
    city: str = "Київ"

    @model_validator(mode="after")
    def _text_or_items(self) -> "BasketIn":
        if not self.items and not self.text.strip():
            raise ValueError("either text or items is required")
        return self


# ---------- Вихід: кошики ----------
class StoreNearby(BaseModel):
    store_id: str
    alt_store_ids: list[str] = Field(default_factory=list, description="Інші ID того ж магазину (з модуля geo)")
    chain: str
    chain_name: str | None = Field(None, description="«Сільпо», «NOVUS» — для показу")
    name: str
    address: str | None = None
    lat: float
    lng: float
    distance_km: float = Field(description="Відстань маршрутом (модуль geo)")
    duration_min: float = Field(description="Час у дорозі для travel_mode, хв (з geo — з десятими)")
    estimated: bool = Field(False, description="true — маршрут оцінено за прямою, показуйте «≈»")
    maps_url: str


class BasketLine(BaseModel):
    requested: str = Field(description="name позиції з ParsedRequest, яку закриває цей товар")
    product_id: int
    title: str
    brand: str | None = None
    img_url: str | None = None
    store_id: str
    pack_qty: float | None = None
    pack_unit: str | None = None
    packs: int
    price: Money = Field(description="грн за пачку")
    old_price: Money | None = None
    promo_percent: int | None = None
    unit_price: Money | None = Field(None, description="грн за кг / л / шт")
    unit_price_label: str
    line_total: Money
    tags: list[str] = Field(default_factory=list)
    note: str | None = Field(None, description="Пояснення для UI, напр. шрінкфляція")


class MissingItem(BaseModel):
    name: str
    reason: str = Field(description="not_found | filtered_by_composition — текст для людини формує UI")


class Basket(BaseModel):
    type: Literal["nearest", "cheapest", "smart_split"]
    stores: list[StoreNearby] = Field(description="1 магазин, або 2 для smart_split")
    lines: list[BasketLine]
    total: Money
    saving: Money = Field(description="Порівняно з найдорожчим із варіантів в одному магазині")
    within_budget: bool
    missing: list[MissingItem] = Field(default_factory=list)


class BasketOut(BaseModel):
    parsed: ParsedRequest = Field(description="Як агент зрозумів запит: для екрана «Я зрозумів так»")
    parser: Literal["llm", "rules", "items"] = Field(
        description="llm — розбір Claude; rules — LLM недоступна, рецепти не розкладаються; items — список з екрана 2"
    )
    stores_considered: int
    baskets: list[Basket] = Field(max_length=3)
    explanation: str
    warnings: list[str] = Field(default_factory=list)
