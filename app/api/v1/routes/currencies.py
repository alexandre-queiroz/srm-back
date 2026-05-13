import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import currency_repository
from app.schemas.currency import CurrencyCreate, CurrencyResponse, CurrencyUpdate

router = APIRouter(prefix="/currencies", tags=["currencies"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[CurrencyResponse], summary="Listar moedas")
def list_currencies(
    current_user: CurrentUser,
    db: DbDep,
    code: str | None = Query(None),
    code_op: str | None = Query(
        None, description="Operador: startswith, endswith, equal, different, contains (padrão)"
    ),
    name: str | None = Query(None),
    name_op: str | None = Query(
        None, description="Operador: startswith, endswith, equal, different, contains (padrão)"
    ),
    active_only: bool = Query(False),
) -> list[CurrencyResponse]:
    currencies = currency_repository.list_currencies(
        db, code=code, code_op=code_op, name=name, name_op=name_op, active_only=active_only
    )
    return [CurrencyResponse.model_validate(c) for c in currencies]


@router.post("", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar moeda")
def create_currency(
    payload: CurrencyCreate,
    current_user: CurrentUser,
    db: DbDep,
) -> CurrencyResponse:
    existing = currency_repository.get_by_code(db, payload.code.upper())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Moeda {payload.code.upper()} já cadastrada.")
    currency = currency_repository.create(
        db, code=payload.code, name=payload.name, symbol=payload.symbol, is_base=payload.is_base
    )
    db.commit()
    db.refresh(currency)
    return CurrencyResponse.model_validate(currency)


@router.patch("/{currency_id}", response_model=CurrencyResponse, summary="Atualizar moeda")
def update_currency(
    currency_id: uuid.UUID,
    payload: CurrencyUpdate,
    current_user: CurrentUser,
    db: DbDep,
) -> CurrencyResponse:
    currency = currency_repository.get_by_id(db, currency_id)
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moeda não encontrada.")
    currency_repository.update(db, currency, **payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(currency)
    return CurrencyResponse.model_validate(currency)
