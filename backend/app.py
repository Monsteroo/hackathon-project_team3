"""FastAPI-застосунок модуля «Голос + Геолокація».

Локально:  .venv/bin/uvicorn backend.app:app --reload
На Vercel: api/index.py імпортує `app`, vercel.json перенаправляє /api/* сюди.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="VoiceCart AI — Voice & Geo API", version="0.1.0")

# Фронт на Vercel живе на тому ж домені; CORS потрібен для локального Vite (5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
