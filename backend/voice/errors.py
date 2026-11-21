from __future__ import annotations


class VoiceError(Exception):
    """Помилка з кодом, за яким фронт вирішує, що показати (fallback Web Speech / ручний ввід)."""

    def __init__(self, code: str, message: str, status: int = 502, fallback: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fallback = fallback  # true → фронт пропонує Web Speech або ручний ввід

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "fallback": self.fallback}
