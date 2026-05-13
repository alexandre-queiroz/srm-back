from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.exchange_rate_service import ExchangeRateError, StaleRateError, collect_rate

router = APIRouter(prefix="/internal", tags=["internal"])

DbDep = Annotated[Session, Depends(get_db)]


def _verify_cron(authorization: str = Header(...)) -> None:
    expected = f"Bearer {settings.CRON_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.get(
    "/collect-rates",
    status_code=status.HTTP_200_OK,
    summary="Cron: coleta taxa USD/BRL",
    description="Chamado pelo Vercel Cron. Protegido por CRON_SECRET.",
)
def cron_collect_rates(
    db: DbDep,
    _: None = Depends(_verify_cron),
) -> dict:
    try:
        record = collect_rate(db)
        return {"status": "ok", "rate": str(record.rate), "source": record.source}
    except StaleRateError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ExchangeRateError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
