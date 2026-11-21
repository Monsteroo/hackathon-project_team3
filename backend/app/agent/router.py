from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.agent import service
from app.agent.schemas import BasketIn, BasketOut, ParsedRequest, ParseIn
from app.db import SessionDep

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/parse", response_model=ParsedRequest)
async def parse(body: ParseIn) -> ParsedRequest:
    """Лише розбір тексту: для екрана «Я зрозумів так» і для евалів. До БД не звертається."""
    return await service.parse(body.text)


@router.post("/basket", response_model=BasketOut)
async def basket(body: BasketIn, session: SessionDep) -> BasketOut:
    """Текст запиту + координати → до 3 кошиків (найближчий, найвигідніший, Smart Split) з цінами каталогу."""
    try:
        return await service.build(session, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (SQLAlchemyError, OSError) as exc:  # БД недоступна: не 500, а зрозуміла 503 для фронту
        raise HTTPException(status_code=503, detail=f"database unavailable: {type(exc).__name__}") from exc
