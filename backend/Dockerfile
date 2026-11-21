# VoiceCart backend: FastAPI + нічний ETL у тому самому процесі.
# Збірка з backend/:  docker build -t voicecart-backend .
FROM python:3.12-slim

# uv тієї самої версії, що й у команди локально
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Спершу лише залежності: шар кешується, поки не змінився uv.lock
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

# Не root: якщо щось зламають через API, прав у контейнері мінімум
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8000
EXPOSE 8000

# Міграції під час кожного старту безпечні: runner бере advisory lock і застосовує лише нові файли.
# PORT задає платформа (Render: 10000); локально — 8000.
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
