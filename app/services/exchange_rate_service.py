from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import get_tracer
from app.models.exchange_rate import ExchangeRate

tracer = get_tracer()

TIMEOUT = 10.0


class ExchangeRateError(Exception):
    pass


class StaleRateError(ExchangeRateError):
    pass


def _fetch_rate_from_url(url: str) -> Decimal:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    # AwesomeAPI: {"USDBRL": {"bid": "5.10"}}
    if "USDBRL" in data:
        return Decimal(str(data["USDBRL"]["bid"]))

    # BCB PTAX: [{"cotacaoCompra": 5.10}]
    if isinstance(data, list) and data and "cotacaoCompra" in data[0]:
        return Decimal(str(data[0]["cotacaoCompra"]))

    raise ExchangeRateError(f"Formato de resposta desconhecido: {list(data.keys())[:3]}")


def collect_rate(db: Session) -> ExchangeRate:
    with tracer.start_as_current_span("exchange_rate.collect") as span:
        source = "primary"
        rate: Decimal | None = None

        try:
            rate = _fetch_rate_from_url(settings.EXCHANGE_RATE_PRIMARY_URL)
            span.set_attribute("fx.source", "primary")
        except Exception as primary_exc:
            span.add_event("primary_failed", {"error": str(primary_exc)})
            try:
                rate = _fetch_rate_from_url(settings.EXCHANGE_RATE_SECONDARY_URL)
                source = "secondary"
                span.set_attribute("fx.source", "secondary")
            except Exception as secondary_exc:
                span.add_event("secondary_failed", {"error": str(secondary_exc)})

        if rate is None:
            _mark_latest_stale(db)
            db.commit()
            span.set_attribute("fx.stale", True)
            raise StaleRateError("Ambas as fontes de câmbio falharam. Taxa marcada como stale.")

        record = ExchangeRate(
            from_currency="USD",
            to_currency="BRL",
            rate=rate,
            source=source,
            is_stale=False,
            collected_at=datetime.now(UTC),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        span.set_attribute("fx.rate", float(rate))
        return record


def _mark_latest_stale(db: Session) -> None:
    latest = get_latest(db, from_currency="USD", to_currency="BRL")
    if latest and not latest.is_stale:
        latest.is_stale = True


def get_latest(db: Session, from_currency: str = "USD", to_currency: str = "BRL") -> ExchangeRate | None:
    today = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
    return (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.collected_at < today,
        )
        .order_by(ExchangeRate.collected_at.desc())
        .first()
    )


def get_current_rate(db: Session, from_currency: str = "USD", to_currency: str = "BRL") -> ExchangeRate:
    record = get_latest(db, from_currency, to_currency)
    if record is None:
        raise ExchangeRateError(f"Nenhuma taxa {from_currency}/{to_currency} encontrada. Execute o job de câmbio.")
    if record.is_stale:
        raise StaleRateError(
            f"Taxa {from_currency}/{to_currency} está stale desde {record.collected_at.isoformat()}. "
            "Operações cross-currency bloqueadas até nova coleta."
        )
    return record


def set_rate_manual(db: Session, rate: Decimal) -> ExchangeRate:
    record = ExchangeRate(
        from_currency="USD",
        to_currency="BRL",
        rate=rate,
        source="manual",
        is_stale=False,
        collected_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
