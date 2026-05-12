from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.exchange_rate_service import (
    ExchangeRateError,
    StaleRateError,
    _fetch_rate_from_url,
    collect_rate,
    get_current_rate,
    set_rate_manual,
)


class TestFetchRateFromUrl:
    def test_parses_awesomeapi_format(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"USDBRL": {"bid": "5.1234"}}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            result = _fetch_rate_from_url("http://fake-url")

        assert result == Decimal("5.1234")

    def test_parses_bcb_format(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"cotacaoCompra": 5.08}]
        mock_response.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            result = _fetch_rate_from_url("http://fake-url")

        assert result == Decimal("5.08")

    def test_unknown_format_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            with pytest.raises(ExchangeRateError, match="Formato de resposta desconhecido"):
                _fetch_rate_from_url("http://fake-url")


class TestCollectRate:
    def _make_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        return db

    def test_collects_from_primary(self):
        db = self._make_db()
        with patch("app.services.exchange_rate_service._fetch_rate_from_url", return_value=Decimal("5.10")):
            record = collect_rate(db)

        assert record.rate == Decimal("5.10")
        assert record.source == "primary"
        assert record.is_stale is False
        db.commit.assert_called_once()

    def test_falls_back_to_secondary_when_primary_fails(self):
        db = self._make_db()

        def side_effect(url):
            if "primary" in url:
                raise ConnectionError("timeout")
            return Decimal("5.20")

        with (
            patch("app.services.exchange_rate_service.settings") as mock_settings,
            patch("app.services.exchange_rate_service._fetch_rate_from_url", side_effect=side_effect),
        ):
            mock_settings.EXCHANGE_RATE_PRIMARY_URL = "http://primary"
            mock_settings.EXCHANGE_RATE_SECONDARY_URL = "http://secondary"
            record = collect_rate(db)

        assert record.source == "secondary"
        assert record.rate == Decimal("5.20")

    def test_marks_stale_when_both_fail(self):
        existing = MagicMock()
        existing.is_stale = False
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing

        with patch("app.services.exchange_rate_service._fetch_rate_from_url", side_effect=ConnectionError("down")):
            with pytest.raises(StaleRateError):
                collect_rate(db)

        assert existing.is_stale is True
        db.commit.assert_called_once()


class TestGetCurrentRate:
    def test_returns_record_when_fresh(self):
        record = MagicMock()
        record.is_stale = False
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = record

        result = get_current_rate(db)
        assert result is record

    def test_raises_when_no_record(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with pytest.raises(ExchangeRateError, match="Nenhuma taxa"):
            get_current_rate(db)

    def test_raises_stale_error_when_stale(self):
        record = MagicMock()
        record.is_stale = True
        record.collected_at = datetime.now(UTC)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = record

        with pytest.raises(StaleRateError, match="stale"):
            get_current_rate(db)


class TestSetRateManual:
    def test_creates_record_with_manual_source(self):
        db = MagicMock()
        record = set_rate_manual(db, Decimal("5.05"))

        assert record.rate == Decimal("5.05")
        assert record.source == "manual"
        assert record.is_stale is False
        assert record.from_currency == "USD"
        assert record.to_currency == "BRL"
        db.commit.assert_called_once()
