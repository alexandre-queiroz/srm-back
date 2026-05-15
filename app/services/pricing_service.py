from abc import ABC, abstractmethod
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.product_type import ProductType
from app.models.system_param import SystemParam

ANNUAL_TO_DAILY = Decimal("365")


class PricingError(Exception):
    pass


class PricingResult:
    def __init__(
        self,
        face_value: Decimal,
        present_value: Decimal,
        present_value_raw: Decimal,
        term_days: int,
        base_rate_annual: Decimal,
        spread_annual: Decimal,
        base_rate_daily: Decimal,
        spread_daily: Decimal,
    ):
        self.face_value = face_value
        # Rounded to 2 decimal places — use for display and BRL-only settlement.
        self.present_value = present_value
        # Full-precision PV — use for cross-currency intermediate calculations
        # to avoid accumulated rounding error before the FX conversion step.
        self.present_value_raw = present_value_raw
        self.term_days = term_days
        self.base_rate_annual = base_rate_annual
        self.spread_annual = spread_annual
        self.base_rate_daily = base_rate_daily
        self.spread_daily = spread_daily
        self.discount = face_value - present_value


# ---------------------------------------------------------------------------
# Strategy interface
# ---------------------------------------------------------------------------


class PricingStrategy(ABC):
    @abstractmethod
    def price(
        self,
        db: Session,
        face_value: Decimal,
        term_days: int,
        product_type_id,
    ) -> PricingResult:
        """Return a fully populated PricingResult."""


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------


class CompoundDiscountStrategy(PricingStrategy):
    """
    VP = VF / (1 + base_rate_daily + spread_daily) ^ term_days

    Base rate is read from SystemParam('base_rate_annual').
    Spread is read from the ProductType record.
    Pass ``prefetched_base_rate`` when pricing many items in a loop to avoid
    repeated reads of the same system parameter row.
    """

    def __init__(self, prefetched_base_rate: tuple[Decimal, Decimal] | None = None) -> None:
        self._prefetched_base_rate = prefetched_base_rate

    def price(self, db: Session, face_value: Decimal, term_days: int, product_type_id) -> PricingResult:
        base_rate_daily, base_rate_annual = self._prefetched_base_rate or _get_base_rate(db)
        spread_daily, spread_annual = _get_spread(db, product_type_id)
        pv_raw = _calculate_present_value_raw(face_value, term_days, base_rate_daily, spread_daily)
        pv = pv_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return PricingResult(
            face_value=face_value,
            present_value=pv,
            present_value_raw=pv_raw,
            term_days=term_days,
            base_rate_annual=base_rate_annual,
            spread_annual=spread_annual,
            base_rate_daily=base_rate_daily,
            spread_daily=spread_daily,
        )


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

_DEFAULT_STRATEGY: PricingStrategy = CompoundDiscountStrategy()


def get_strategy(product_type_id=None) -> PricingStrategy:  # noqa: ARG001
    """
    Returns the pricing strategy for a given product type.
    Currently all product types use CompoundDiscountStrategy; extend this
    registry when new formula types are introduced.
    """
    return _DEFAULT_STRATEGY


def create_batch_strategy(db: Session) -> CompoundDiscountStrategy:
    """
    Returns a CompoundDiscountStrategy with the base rate pre-fetched.
    Use this when pricing many receivables in a single request/transaction
    to avoid N identical queries against system_params.
    """
    return CompoundDiscountStrategy(prefetched_base_rate=_get_base_rate(db))


# ---------------------------------------------------------------------------
# Pure calculation helpers (stateless, easy to unit-test)
# ---------------------------------------------------------------------------


def _get_base_rate(db: Session) -> tuple[Decimal, Decimal]:
    param = db.query(SystemParam).filter(SystemParam.key == "base_rate_annual").first()
    if param is None:
        raise PricingError("Parâmetro 'base_rate_annual' não encontrado. Execute o seed.")
    annual = param.value
    daily = (1 + annual) ** (Decimal("1") / ANNUAL_TO_DAILY) - 1
    return daily, annual


def _get_spread(db: Session, product_type_id) -> tuple[Decimal, Decimal]:
    pt = (
        db.query(ProductType)
        .filter(
            ProductType.id == product_type_id,
            ProductType.is_active == True,  # noqa: E712
        )
        .first()
    )
    if pt is None:
        raise PricingError(f"ProductType {product_type_id} não encontrado ou inativo.")
    annual = pt.spread
    daily = (1 + annual) ** (Decimal("1") / ANNUAL_TO_DAILY) - 1
    return daily, annual


def calculate_term_days(due_date: date, reference_date: date | None = None) -> int:
    ref = reference_date or date.today()
    days = (due_date - ref).days
    return max(days, 1)


def _calculate_present_value_raw(
    face_value: Decimal,
    term_days: int,
    base_rate_daily: Decimal,
    spread_daily: Decimal,
) -> Decimal:
    """Full-precision PV — no rounding. Use for intermediate cross-currency steps."""
    factor = (1 + base_rate_daily + spread_daily) ** Decimal(str(term_days))
    return face_value / factor


def calculate_present_value(
    face_value: Decimal,
    term_days: int,
    base_rate_daily: Decimal,
    spread_daily: Decimal,
) -> Decimal:
    """Rounded PV (2 decimal places). Public API kept for backward compatibility."""
    return _calculate_present_value_raw(face_value, term_days, base_rate_daily, spread_daily).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


# ---------------------------------------------------------------------------
# Public API — delegates to the registered strategy
# ---------------------------------------------------------------------------


def price_receivable(
    db: Session,
    face_value: Decimal,
    due_date: date,
    product_type_id,
    reference_date: date | None = None,
    strategy: PricingStrategy | None = None,
) -> PricingResult:
    if strategy is None:
        strategy = get_strategy(product_type_id)
    term_days = calculate_term_days(due_date, reference_date)
    return strategy.price(db, face_value, term_days, product_type_id)
