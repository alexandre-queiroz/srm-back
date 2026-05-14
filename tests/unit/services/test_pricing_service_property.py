from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.pricing_service import calculate_present_value, calculate_term_days

MAX_EXAMPLES = 5000

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

face_values = st.decimals(
    min_value="0.01",
    max_value="10000000.00",
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Daily rates equivalent to 0%–80% annual (covers well beyond any realistic spread)
daily_rates = st.decimals(
    min_value="0.000000",
    max_value="0.001700",
    places=6,
    allow_nan=False,
    allow_infinity=False,
)

term_days = st.integers(min_value=1, max_value=1825)  # up to 5 years


# ---------------------------------------------------------------------------
# calculate_present_value — invariants
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, term=term_days, base_rate=daily_rates, spread=daily_rates)
def test_pv_never_exceeds_face_value(face_value, term, base_rate, spread):
    pv = calculate_present_value(face_value, term, base_rate, spread)
    assert pv <= face_value


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, term=term_days, base_rate=daily_rates, spread=daily_rates)
def test_pv_always_non_negative(face_value, term, base_rate, spread):
    # VP pode arredondar para 0.00 em casos extremos (ex: VF=0.01, prazo=589d, spread alto).
    # O sistema não impõe valor mínimo de VP na camada matemática — isso é responsabilidade
    # da validação de negócio antes de aceitar o recebível para antecipação.
    pv = calculate_present_value(face_value, term, base_rate, spread)
    assert pv >= Decimal("0")


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, term=term_days, base_rate=daily_rates, spread=daily_rates)
def test_discount_always_non_negative(face_value, term, base_rate, spread):
    pv = calculate_present_value(face_value, term, base_rate, spread)
    assert face_value - pv >= Decimal("0")


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, term=term_days, base_rate=daily_rates, spread=daily_rates)
def test_result_has_two_decimal_places(face_value, term, base_rate, spread):
    pv = calculate_present_value(face_value, term, base_rate, spread)
    assert pv == pv.quantize(Decimal("0.01"))


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, term=term_days)
def test_zero_rates_returns_face_value(face_value, term):
    pv = calculate_present_value(face_value, term, Decimal("0"), Decimal("0"))
    assert pv == face_value


@settings(max_examples=MAX_EXAMPLES)
@given(face_value=face_values, base_rate=daily_rates, spread=daily_rates)
def test_longer_term_produces_lower_or_equal_pv(face_value, base_rate, spread):
    # t2 > t1 → pv(t2) ≤ pv(t1)
    pv_short = calculate_present_value(face_value, 30, base_rate, spread)
    pv_long = calculate_present_value(face_value, 360, base_rate, spread)
    assert pv_long <= pv_short


@settings(max_examples=MAX_EXAMPLES)
@given(
    face_value=face_values,
    term=term_days,
    base_rate=daily_rates,
    extra=st.decimals(min_value="0.000001", max_value="0.000500", places=6, allow_nan=False, allow_infinity=False),
)
def test_higher_spread_produces_lower_or_equal_pv(face_value, term, base_rate, extra):
    # spread2 > spread1 → pv(spread2) ≤ pv(spread1)
    spread_low = Decimal("0.000100")
    spread_high = spread_low + extra
    pv_low = calculate_present_value(face_value, term, base_rate, spread_low)
    pv_high = calculate_present_value(face_value, term, base_rate, spread_high)
    assert pv_high <= pv_low


# ---------------------------------------------------------------------------
# calculate_term_days — invariants
# ---------------------------------------------------------------------------


@settings(max_examples=MAX_EXAMPLES)
@given(days_ahead=st.integers(min_value=1, max_value=1825))
def test_term_days_future_date_correct(days_ahead):
    ref = date(2026, 1, 1)
    due = ref + timedelta(days=days_ahead)
    assert calculate_term_days(due, reference_date=ref) == days_ahead


@settings(max_examples=MAX_EXAMPLES)
@given(days_past=st.integers(min_value=0, max_value=365))
def test_term_days_past_or_same_returns_one(days_past):
    ref = date(2026, 6, 1)
    due = ref - timedelta(days=days_past)
    assert calculate_term_days(due, reference_date=ref) == 1


@settings(max_examples=MAX_EXAMPLES)
@given(
    days_ahead=st.integers(min_value=1, max_value=1825),
    days_past=st.integers(min_value=0, max_value=365),
)
def test_term_days_always_at_least_one(days_ahead, days_past):
    ref = date(2026, 6, 1)
    for due in [ref + timedelta(days=days_ahead), ref - timedelta(days=days_past)]:
        assert calculate_term_days(due, reference_date=ref) >= 1
