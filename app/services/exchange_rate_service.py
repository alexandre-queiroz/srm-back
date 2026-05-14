from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.core.observability import get_tracer
from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate

tracer = get_tracer()

TIMEOUT = 10.0


class ExchangeRateError(Exception):
    pass


class StaleRateError(ExchangeRateError):
    pass


def _primary_url(from_currency: str, to_currency: str) -> str:
    return f"https://economia.awesomeapi.com.br/json/last/{from_currency}-{to_currency}"


def _secondary_url(from_currency: str, _to_currency: str) -> str:
    return f"https://open.er-api.com/v6/latest/{from_currency}"


def _fetch_rate(url: str, from_currency: str, to_currency: str) -> Decimal:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    # AwesomeAPI: {"USDBRL": {"bid": "5.10"}}
    pair_key = f"{from_currency}{to_currency}"
    if pair_key in data:
        return Decimal(str(data[pair_key]["bid"]))

    # open.er-api: {"rates": {"BRL": 5.10}}
    if "rates" in data and to_currency in data["rates"]:
        return Decimal(str(data["rates"][to_currency]))

    raise ExchangeRateError(f"Formato de resposta desconhecido para {from_currency}/{to_currency}")


def collect_rate(db: Session, from_currency: str = "USD", to_currency: str = "BRL") -> ExchangeRate:
    with tracer.start_as_current_span("exchange_rate.collect") as span:
        span.set_attribute("fx.pair", f"{from_currency}/{to_currency}")
        source = "primary"
        rate: Decimal | None = None

        try:
            rate = _fetch_rate(_primary_url(from_currency, to_currency), from_currency, to_currency)
            span.set_attribute("fx.source", "primary")
        except Exception as primary_exc:
            span.add_event("primary_failed", {"error": str(primary_exc)})
            try:
                rate = _fetch_rate(_secondary_url(from_currency, to_currency), from_currency, to_currency)
                source = "secondary"
                span.set_attribute("fx.source", "secondary")
            except Exception as secondary_exc:
                span.add_event("secondary_failed", {"error": str(secondary_exc)})

        if rate is None:
            _mark_latest_stale(db, from_currency, to_currency)
            db.commit()
            span.set_attribute("fx.stale", True)
            raise StaleRateError(
                f"Ambas as fontes falharam para {from_currency}/{to_currency}. Taxa marcada como stale."
            )

        _mark_latest_stale(db, from_currency, to_currency)
        record = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
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


def collect_all_rates(db: Session, to_currency: str = "BRL") -> list[ExchangeRate]:
    """Collect rates for all active non-base currencies against to_currency."""
    non_base = db.query(Currency).filter(Currency.is_active == True, Currency.is_base == False).all()  # noqa: E712
    results = []
    for currency in non_base:
        try:
            record = collect_rate(db, from_currency=currency.code, to_currency=to_currency)
            results.append(record)
        except (ExchangeRateError, StaleRateError):
            pass
    return results


def _mark_latest_stale(db: Session, from_currency: str = "USD", to_currency: str = "BRL") -> None:
    latest = get_latest(db, from_currency=from_currency, to_currency=to_currency)
    if latest and not latest.is_stale:
        latest.is_stale = True


def get_latest(db: Session, from_currency: str = "USD", to_currency: str = "BRL") -> ExchangeRate | None:
    return (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
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


def set_rate_manual(db: Session, rate: Decimal, from_currency: str = "USD", to_currency: str = "BRL") -> ExchangeRate:
    _mark_latest_stale(db, from_currency, to_currency)
    record = ExchangeRate(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
        source="manual",
        is_stale=False,
        collected_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
