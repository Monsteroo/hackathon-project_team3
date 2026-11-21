"""Формат ID магазинів: наш `zakaz:48201031` / `silpo:<uuid>` ↔ сирий з API Учасниці 2 та агента."""

import re

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def normalize_store_id(raw: str, source: str | None = None) -> str:
    """Числовий ID — Zakaz.ua, uuid — Сільпо (branchId). `source`, якщо відомий, має пріоритет."""
    sid = str(raw).strip()
    if ":" in sid:
        src, _, rest = sid.partition(":")
        return f"{src.lower()}:{rest.strip()}"
    if source:
        return f"{source.strip().lower()}:{sid.lower() if UUID_RE.match(sid) else sid}"
    if sid.isdigit():
        return f"zakaz:{sid}"
    if UUID_RE.match(sid):
        return f"silpo:{sid.lower()}"
    return sid
