from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.pricing_service import (
    PricingError,
    calculate_present_value,
    calculate_term_days,
    price_receivable,
)


class TestCalculateTermDays:
    def test_future_date_returns_correct_days(self):
        result = calculate_term_days(date(2026, 6, 1), reference_date=date(2026, 5, 1))
        assert result == 31

    def test_same_day_returns_one(self):
        result = calculate_term_days(date(2026, 5, 1), reference_date=date(2026, 5, 1))
        assert result == 1

    def test_past_due_date_returns_one(self):
        result = calculate_term_days(date(2026, 4, 1), reference_date=date(2026, 5, 1))
        assert result == 1


class TestCalculatePresentValue:
    def test_zero_rates_returns_face_value(self):
        pv = calculate_present_value(
            face_value=Decimal("10000.00"),
            term_days=30,
            base_rate_daily=Decimal("0"),
            spread_daily=Decimal("0"),
        )
        assert pv == Decimal("10000.00")

    def test_pv_less_than_face_value_with_positive_rates(self):
        pv = calculate_present_value(
            face_value=Decimal("10000.00"),
            term_days=30,
            base_rate_daily=Decimal("0.000355"),
            spread_daily=Decimal("0.000075"),
        )
        assert pv < Decimal("10000.00")

    def test_result_has_two_decimal_places(self):
        pv = calculate_present_value(
            face_value=Decimal("10000.00"),
            term_days=30,
            base_rate_daily=Decimal("0.000355"),
            spread_daily=Decimal("0.000075"),
        )
        assert pv == pv.quantize(Decimal("0.01"))

    def test_longer_term_produces_lower_pv(self):
        kwargs = dict(
            face_value=Decimal("10000.00"),
            base_rate_daily=Decimal("0.000355"),
            spread_daily=Decimal("0.000075"),
        )
        pv_30 = calculate_present_value(term_days=30, **kwargs)
        pv_90 = calculate_present_value(term_days=90, **kwargs)
        assert pv_90 < pv_30

    def test_known_value(self):
        # VF=10000, 365 days, annual rate 13.75% + spread 2.5% = 16.25%
        # daily base = (1.1375)^(1/365)-1, daily spread = (1.025)^(1/365)-1
        # factor = (1 + daily_base + daily_spread)^365 ≈ 1.1625
        # VP ≈ 10000 / 1.1625 ≈ 8602.15
        base_daily = (1 + Decimal("0.13750000")) ** (Decimal("1") / Decimal("365")) - 1
        spread_daily = (1 + Decimal("0.02500000")) ** (Decimal("1") / Decimal("365")) - 1
        pv = calculate_present_value(
            face_value=Decimal("10000.00"),
            term_days=365,
            base_rate_daily=base_daily,
            spread_daily=spread_daily,
        )
        assert Decimal("8500") < pv < Decimal("8700")


def _make_db(base_rate_annual: str = "0.13750000", spread: str = "0.02500000"):
    from app.models.product_type import ProductType
    from app.models.system_param import SystemParam

    param = MagicMock(spec=SystemParam)
    param.value = Decimal(base_rate_annual)

    pt = MagicMock(spec=ProductType)
    pt.spread = Decimal(spread)
    pt.id = "some-id"

    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.side_effect = [param, pt]
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


class TestPriceReceivable:
    def test_returns_pricing_result(self):
        db = _make_db()
        result = price_receivable(
            db=db,
            face_value=Decimal("10000.00"),
            due_date=date(2027, 5, 12),
            product_type_id="some-id",
            reference_date=date(2026, 5, 12),
        )
        assert result.face_value == Decimal("10000.00")
        assert result.present_value > Decimal("0")
        assert result.present_value < result.face_value
        assert result.discount == result.face_value - result.present_value
        assert result.term_days == 365

    def test_missing_base_rate_raises(self):
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        with pytest.raises(PricingError, match="base_rate_annual"):
            price_receivable(
                db=db,
                face_value=Decimal("10000.00"),
                due_date=date(2027, 5, 12),
                product_type_id="missing-id",
                reference_date=date(2026, 5, 12),
            )
