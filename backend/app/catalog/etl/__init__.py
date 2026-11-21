"""Нічний ETL модуля catalog: Zakaz.ua + Сільпо -> нормалізовані товари й ціни в БД.

Запуск вручну (з backend/):  uv run python -m app.catalog.etl --help
За розкладом: app.catalog.jobs реєструє запуск у планувальнику FastAPI (за замовчуванням щодня о 03:00 за Києвом).
"""
