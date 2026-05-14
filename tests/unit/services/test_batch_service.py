import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.batch_service import BatchError, ConcurrencyError, confirm_batch, create_batch, preview_batch


def _make_receivable(
    receivable_id=None,
    assignor_id=None,
    status="available",
    product_type_id=None,
    currency_code="BRL",
):
    r = MagicMock()
    r.id = receivable_id or uuid.uuid4()
    r.assignor_id = assignor_id or uuid.uuid4()
    r.drawee_id = uuid.uuid4()
    r.status = status
    r.face_value = Decimal("10000.00")
    r.due_date = date(2027, 1, 1)
    r.currency_code = currency_code
    r.product_type_id = product_type_id or uuid.uuid4()
    r.invoice_key = "35260111222333000181550010001000011123456780"
    r.installment_number = "001"
    return r


def _make_pricing_result(pv="9500.00"):
    from app.services.pricing_service import PricingResult

    return PricingResult(
        face_value=Decimal("10000.00"),
        present_value=Decimal(pv),
        term_days=120,
        base_rate_annual=Decimal("0.1375"),
        spread_annual=Decimal("0.025"),
        base_rate_daily=Decimal("0.000355"),
        spread_daily=Decimal("0.000068"),
    )


class TestCreateBatch:
    def test_empty_receivable_ids_raises(self):
        db = MagicMock()
        with pytest.raises(BatchError, match="ao menos um"):
            create_batch(db, user_id=uuid.uuid4(), assignor_id=uuid.uuid4(), receivable_ids=[])

    def test_receivable_not_found_raises(self):
        db = MagicMock()
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=None):
            with pytest.raises(BatchError, match="não encontrado"):
                create_batch(
                    db,
                    user_id=uuid.uuid4(),
                    assignor_id=uuid.uuid4(),
                    receivable_ids=[uuid.uuid4()],
                )

    def test_wrong_assignor_raises(self):
        assignor_id = uuid.uuid4()
        receivable = _make_receivable(assignor_id=uuid.uuid4())
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=receivable):
            with pytest.raises(BatchError, match="não pertence ao cedente"):
                create_batch(
                    MagicMock(),
                    user_id=uuid.uuid4(),
                    assignor_id=assignor_id,
                    receivable_ids=[receivable.id],
                )

    def test_anticipated_receivable_raises(self):
        assignor_id = uuid.uuid4()
        receivable = _make_receivable(assignor_id=assignor_id, status="anticipated")
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=receivable):
            with pytest.raises(BatchError, match="não pode ser incluído em lote"):
                create_batch(
                    MagicMock(),
                    user_id=uuid.uuid4(),
                    assignor_id=assignor_id,
                    receivable_ids=[receivable.id],
                )

    def test_available_receivable_does_not_change_status(self):
        assignor_id = uuid.uuid4()
        r1 = _make_receivable(assignor_id=assignor_id)
        r2 = _make_receivable(assignor_id=assignor_id)

        db = MagicMock()
        db.execute.return_value = None

        with (
            patch("app.services.batch_service.receivable_repository.get_by_id", side_effect=[r1, r2]),
            patch("app.services.batch_service.batch_repository.create") as mock_create,
        ):
            mock_create.side_effect = lambda db, batch: batch

            create_batch(db, user_id=uuid.uuid4(), assignor_id=assignor_id, receivable_ids=[r1.id, r2.id])

        # Receivables must remain 'available' — no status lock on batch creation
        assert r1.status == "available"
        assert r2.status == "available"
        db.commit.assert_called_once()


class TestPreviewBatch:
    def _make_batch(self, status="pending", receivables=None):
        batch = MagicMock()
        batch.id = uuid.uuid4()
        batch.assignor_id = uuid.uuid4()
        batch.status = status
        batch.receivables = receivables or []
        return batch

    def test_batch_not_found_raises(self):
        with patch("app.services.batch_service.batch_repository.get_by_id", return_value=None):
            with pytest.raises(BatchError, match="não encontrado"):
                preview_batch(MagicMock(), batch_id=uuid.uuid4())

    def test_approved_batch_raises(self):
        batch = self._make_batch(status="approved")
        with patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch):
            with pytest.raises(BatchError, match="não pode ser simulado"):
                preview_batch(MagicMock(), batch_id=batch.id)

    def test_returns_preview_with_correct_totals(self):
        assignor_id = uuid.uuid4()
        r1 = _make_receivable(assignor_id=assignor_id)
        r2 = _make_receivable(assignor_id=assignor_id)
        batch = self._make_batch(receivables=[r1, r2])

        pricing_result = _make_pricing_result("9500.00")

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch(
                "app.services.batch_service.pricing_service.price_receivable",
                return_value=pricing_result,
            ),
        ):
            preview = preview_batch(MagicMock(), batch_id=batch.id)

        assert preview.total_receivables == 2
        assert preview.total_face_value == Decimal("20000.00")
        assert preview.total_present_value == Decimal("19000.00")
        assert len(preview.items) == 2


class TestConfirmBatch:
    def _make_batch(self, status="pending", version=0, receivables=None):
        batch = MagicMock()
        batch.id = uuid.uuid4()
        batch.assignor_id = uuid.uuid4()
        batch.status = status
        batch.version = version
        batch.receivables = receivables or []
        return batch

    def _make_db(self, rowcount=1, locked_status="available"):
        db = MagicMock()
        execute_result = MagicMock()
        execute_result.rowcount = rowcount
        db.execute.return_value = execute_result
        # Mock the FOR UPDATE re-check path in confirm_batch
        locked = MagicMock()
        locked.status = locked_status
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = locked
        return db

    def test_batch_not_found_raises(self):
        with patch("app.services.batch_service.batch_repository.get_by_id", return_value=None):
            with pytest.raises(BatchError, match="não encontrado"):
                confirm_batch(MagicMock(), batch_id=uuid.uuid4(), user_id=uuid.uuid4(), expected_version=0)

    def test_wrong_status_raises(self):
        batch = self._make_batch(status="approved")
        with patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch):
            with pytest.raises(BatchError, match="não pode ser confirmado"):
                confirm_batch(MagicMock(), batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)

    def test_concurrency_error_when_version_mismatch(self):
        assignor_id = uuid.uuid4()
        r = _make_receivable(assignor_id=assignor_id, currency_code="BRL")
        batch = self._make_batch(version=0, receivables=[r])
        db = self._make_db(rowcount=0)  # simulates version mismatch → 0 rows updated

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch(
                "app.services.batch_service.pricing_service.price_receivable",
                return_value=_make_pricing_result(),
            ),
        ):
            with pytest.raises(ConcurrencyError, match="modificado por outro processo"):
                confirm_batch(db, batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)

    def test_confirm_brl_batch_no_fx_needed(self):
        assignor_id = uuid.uuid4()
        r = _make_receivable(assignor_id=assignor_id, currency_code="BRL")
        batch = self._make_batch(version=0, receivables=[r])
        db = self._make_db(rowcount=1)

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch(
                "app.services.batch_service.pricing_service.price_receivable",
                return_value=_make_pricing_result("9500.00"),
            ),
        ):
            confirm_batch(db, batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)

        assert r.status == "anticipated"
        db.commit.assert_called_once()

        # Verify Transaction was bulk-added without FX fields
        added_txn = db.add_all.call_args[0][0][0]
        assert added_txn.exchange_rate_id is None
        assert added_txn.exchange_rate_used is None
        assert added_txn.present_value == Decimal("9500.00")
        assert added_txn.instrument_currency == "BRL"
        assert added_txn.settlement_currency == "BRL"

    def test_confirm_usd_batch_converts_to_brl(self):
        assignor_id = uuid.uuid4()
        r = _make_receivable(assignor_id=assignor_id, currency_code="USD")
        batch = self._make_batch(version=0, receivables=[r])
        db = self._make_db(rowcount=1)

        fx_record = MagicMock()
        fx_record.id = uuid.uuid4()
        fx_record.rate = Decimal("5.20")

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch(
                "app.services.batch_service.pricing_service.price_receivable",
                return_value=_make_pricing_result("9500.00"),
            ),
            patch("app.services.batch_service.get_current_rate", return_value=fx_record),
        ):
            confirm_batch(db, batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)

        added_txn = db.add_all.call_args[0][0][0]
        # 9500.00 USD * 5.20 = 49400.00 BRL
        assert added_txn.present_value == Decimal("49400.00")
        assert added_txn.exchange_rate_id == fx_record.id
        assert added_txn.exchange_rate_used == Decimal("5.20")
        assert added_txn.instrument_currency == "USD"
        assert added_txn.settlement_currency == "BRL"

    def test_rejects_batch_when_receivable_already_anticipated(self):
        assignor_id = uuid.uuid4()
        r = _make_receivable(assignor_id=assignor_id, currency_code="BRL")
        batch = self._make_batch(version=0, receivables=[r])
        db = self._make_db(rowcount=1, locked_status="anticipated")

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch(
                "app.services.batch_service.pricing_service.price_receivable",
                return_value=_make_pricing_result(),
            ),
        ):
            result = confirm_batch(db, batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)

        # Batch should be rejected, not approved, because the receivable was already anticipated
        assert result.status == "rejected"
        db.add_all.assert_not_called()

    def test_stale_fx_raises_batch_error(self):
        from app.services.exchange_rate_service import StaleRateError

        assignor_id = uuid.uuid4()
        r = _make_receivable(assignor_id=assignor_id, currency_code="USD")
        batch = self._make_batch(version=0, receivables=[r])
        db = self._make_db(rowcount=1)

        with (
            patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch),
            patch("app.services.batch_service.get_current_rate", side_effect=StaleRateError("stale")),
        ):
            with pytest.raises(BatchError, match="Taxa de câmbio indisponível"):
                confirm_batch(db, batch_id=batch.id, user_id=uuid.uuid4(), expected_version=0)
