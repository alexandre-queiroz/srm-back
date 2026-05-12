from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.product_type import ProductType
from app.models.system_param import SystemParam

ANNUAL_TO_DAILY = Decimal("365")


class PricingError(Exception):
    pass


def _get_base_rate(db: Session) -> tuple[Decimal, Decimal]:
    param = db.query(SystemParam).filter(SystemParam.key == "base_rate_annual").first()
    if param is None:
        raise PricingError("Parâmetro 'base_rate_annual' não encontrado. Execute o seed.")
    annual = param.value
    daily = (1 + annual) ** (Decimal("1") / ANNUAL_TO_DAILY) - 1
    return daily, annual


def _get_spread(db: Session, product_type_id) -> Decimal:
    pt = db.query(ProductType).filter(
        ProductType.id == product_type_id,
        ProductType.is_active == True,  # noqa: E712
    ).first()
    if pt is None:
        raise PricingError(f"ProductType {product_type_id} não encontrado ou inativo.")
    # Convert annual spread to daily
    annual = pt.spread
    daily = (1 + annual) ** (Decimal("1") / ANNUAL_TO_DAILY) - 1
    return daily, pt.spread


def calculate_term_days(due_date: date, reference_date: date | None = None) -> int:
    ref = reference_date or date.today()
    days = (due_date - ref).days
    return max(days, 1)


def calculate_present_value(
    face_value: Decimal,
    term_days: int,
    base_rate_daily: Decimal,
    spread_daily: Decimal,
) -> Decimal:
    """
    VP = VF / (1 + base_rate_daily + spread_daily) ^ term_days
    Rates are daily equivalents of annual rates.
    """
    factor = (1 + base_rate_daily + spread_daily) ** Decimal(str(term_days))
    pv = face_value / factor
    return pv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PricingResult:
    def __init__(
        self,
        face_value: Decimal,
        present_value: Decimal,
        term_days: int,
        base_rate_annual: Decimal,
        spread_annual: Decimal,
        base_rate_daily: Decimal,
        spread_daily: Decimal,
    ):
        self.face_value = face_value
        self.present_value = present_value
        self.term_days = term_days
        self.base_rate_annual = base_rate_annual
        self.spread_annual = spread_annual
        self.base_rate_daily = base_rate_daily
        self.spread_daily = spread_daily
        self.discount = face_value - present_value


def price_receivable(
    db: Session,
    face_value: Decimal,
    due_date: date,
    product_type_id,
    reference_date: date | None = None,
) -> PricingResult:
    base_rate_daily, base_rate_annual = _get_base_rate(db)
    spread_daily, spread_annual = _get_spread(db, product_type_id)
    term_days = calculate_term_days(due_date, reference_date)

    pv = calculate_present_value(face_value, term_days, base_rate_daily, spread_daily)

    return PricingResult(
        face_value=face_value,
        present_value=pv,
        term_days=term_days,
        base_rate_annual=base_rate_annual,
        spread_annual=spread_annual,
        base_rate_daily=base_rate_daily,
        spread_daily=spread_daily,
    )
