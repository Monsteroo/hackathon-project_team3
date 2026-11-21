class VoiceError(Exception):
    """Помилка з кодом: за `code` фронт показує український текст і вирішує, чи вмикати fallback
    (Web Speech у браузері або ручний ввід). `message` — англійською (правило команди для `detail`)."""

    def __init__(self, code: str, message: str, status: int = 502, fallback: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fallback = fallback

    def to_detail(self) -> dict:
        return {"code": self.code, "message": self.message, "fallback": self.fallback}


def err_summary(e: BaseException) -> str:
    """Для логів: лише тип і HTTP-статус, без тексту запиту користувача."""
    status = getattr(getattr(e, "response", None), "status_code", None)
    return f"{type(e).__name__}{f' HTTP {status}' if status else ''}"
