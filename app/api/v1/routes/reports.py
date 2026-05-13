import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories import report_repository
from app.schemas.report import SettlementReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get(
    "/settlements",
    response_model=SettlementReportResponse,
    summary="Extrato de Liquidação Analítico",
    description=(
        "Retorna o histórico de liquidações com filtros por período, cedente e moeda. " "Usa SQL Nativo otimizado."
    ),
)
def get_settlement_report(
    current_user: CurrentUser,
    db: DbDep,
    start_date: datetime | None = Query(None, description="Data inicial de liquidação"),
    end_date: datetime | None = Query(None, description="Data final de liquidação"),
    assignor_id: uuid.UUID | None = Query(None, description="ID do cedente"),
    currency_code: str | None = Query(None, min_length=3, max_length=3, description="Código da moeda (BRL/USD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> SettlementReportResponse:
    items, summary = report_repository.get_settlement_report(
        db=db,
        start_date=start_date,
        end_date=end_date,
        assignor_id=assignor_id,
        currency_code=currency_code,
        page=page,
        page_size=page_size,
    )

    return SettlementReportResponse(items=items, summary=summary, page=page, page_size=page_size)
