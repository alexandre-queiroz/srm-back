import uuid

from sqlalchemy.orm import Session

from app.models.currency import Currency
from app.repositories._filters import str_filter


def get_by_code(db: Session, code: str) -> Currency | None:
    return db.query(Currency).filter(Currency.code == code).first()


def get_by_id(db: Session, currency_id: uuid.UUID) -> Currency | None:
    return db.query(Currency).filter(Currency.id == currency_id).first()


def list_currencies(
    db: Session,
    code: str | None = None,
    code_op: str | None = None,
    name: str | None = None,
    name_op: str | None = None,
    active_only: bool = False,
) -> list[Currency]:
    q = db.query(Currency)
    if active_only:
        q = q.filter(Currency.is_active == True)  # noqa: E712
    if code:
        q = q.filter(str_filter(Currency.code, code, code_op))
    if name:
        q = q.filter(str_filter(Currency.name, name, name_op))
    return q.order_by(Currency.code).all()


def create(db: Session, code: str, name: str, symbol: str, is_base: bool = False) -> Currency:
    currency = Currency(code=code.upper(), name=name, symbol=symbol, is_base=is_base)
    db.add(currency)
    db.flush()
    return currency


def update(db: Session, currency: Currency, **kwargs) -> Currency:
    for key, value in kwargs.items():
        if value is not None:
            setattr(currency, key, value)
    return currency
