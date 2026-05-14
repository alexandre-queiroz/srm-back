from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.exchange_rate_service import ExchangeRateError, StaleRateError, collect_all_rates

router = APIRouter(prefix="/internal", tags=["internal"])

DbDep = Annotated[Session, Depends(get_db)]


def _verify_cron(authorization: str = Header(...)) -> None:
    expected = f"Bearer {settings.CRON_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.get(
    "/collect-rates",
    status_code=status.HTTP_200_OK,
    summary="Cron: coleta taxas de todas as moedas ativas",
    description="Chamado pelo Vercel Cron. Protegido por CRON_SECRET.",
)
def cron_collect_rates(
    db: DbDep,
    _: None = Depends(_verify_cron),
) -> dict:
    try:
        records = collect_all_rates(db)
        return {
            "status": "ok",
            "collected": [{"pair": f"{r.from_currency}/{r.to_currency}", "rate": str(r.rate)} for r in records],
        }
    except StaleRateError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ExchangeRateError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
