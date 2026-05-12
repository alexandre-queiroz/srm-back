from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.schemas.exchange_rate import ExchangeRateResponse
from app.services.exchange_rate_service import (
    ExchangeRateError,
    StaleRateError,
    collect_rate,
    get_latest,
    set_rate_manual,
)

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post(
    "/collect",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Disparar coleta de taxa USD/BRL",
    description="Coleta primária com fallback. Se ambas falharem, taxa vigente é marcada como stale.",
)
def trigger_collect(current_user: CurrentUser, db: DbDep) -> ExchangeRateResponse:
    try:
        record = collect_rate(db)
    except StaleRateError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ExchangeRateError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return ExchangeRateResponse.model_validate(record)


@router.post(
    "/manual",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inserir taxa manualmente",
    description="Permite ao operador inserir taxa USD/BRL manualmente. Útil em caso de falha das fontes externas.",
)
def manual_rate(
    current_user: CurrentUser,
    db: DbDep,
    rate: Decimal,
) -> ExchangeRateResponse:
    if rate <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Taxa deve ser positiva.")
    record = set_rate_manual(db, rate)
    return ExchangeRateResponse.model_validate(record)


@router.get(
    "/latest",
    response_model=ExchangeRateResponse,
    summary="Taxa USD/BRL mais recente",
)
def latest_rate(current_user: CurrentUser, db: DbDep) -> ExchangeRateResponse:
    record = get_latest(db)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma taxa encontrada.")
    return ExchangeRateResponse.model_validate(record)
