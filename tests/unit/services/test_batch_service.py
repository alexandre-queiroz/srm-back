import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.batch_service import BatchError, create_batch, preview_batch


def _make_receivable(
    receivable_id=None,
    assignor_id=None,
    status="available",
    product_type_id=None,
):
    r = MagicMock()
    r.id = receivable_id or uuid.uuid4()
    r.assignor_id = assignor_id or uuid.uuid4()
    r.drawee_id = uuid.uuid4()
    r.status = status
    r.face_value = Decimal("10000.00")
    r.due_date = date(2027, 1, 1)
    r.currency_code = "BRL"
    r.product_type_id = product_type_id or uuid.uuid4()
    r.invoice_key = "35260111222333000181550010001000011123456780"
    r.installment_number = "001"
    return r


class TestCreateBatch:
    def test_empty_receivable_ids_raises(self):
        db = MagicMock()
        with pytest.raises(BatchError, match="ao menos um"):
            create_batch(db, user_id=uuid.uuid4(), assignor_id=uuid.uuid4(), receivable_ids=[])

    def test_receivable_not_found_raises(self):
        db = MagicMock()
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=None):
            with pytest.raises(BatchError, match="não encontrado"):
                create_batch(db, user_id=uuid.uuid4(), assignor_id=uuid.uuid4(), receivable_ids=[uuid.uuid4()])

    def test_wrong_assignor_raises(self):
        assignor_id = uuid.uuid4()
        receivable = _make_receivable(assignor_id=uuid.uuid4())  # different assignor
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=receivable):
            with pytest.raises(BatchError, match="não pertence ao cedente"):
                create_batch(MagicMock(), user_id=uuid.uuid4(), assignor_id=assignor_id, receivable_ids=[receivable.id])

    def test_unavailable_receivable_raises(self):
        assignor_id = uuid.uuid4()
        receivable = _make_receivable(assignor_id=assignor_id, status="in_batch")
        with patch("app.services.batch_service.receivable_repository.get_by_id", return_value=receivable):
            with pytest.raises(BatchError, match="não está disponível"):
                create_batch(MagicMock(), user_id=uuid.uuid4(), assignor_id=assignor_id, receivable_ids=[receivable.id])

    def test_creates_batch_and_updates_status(self):
        assignor_id = uuid.uuid4()
        r1 = _make_receivable(assignor_id=assignor_id)
        r2 = _make_receivable(assignor_id=assignor_id)

        db = MagicMock()
        db.execute.return_value = None

        with patch("app.services.batch_service.receivable_repository.get_by_id", side_effect=[r1, r2]), \
             patch("app.services.batch_service.batch_repository.create") as mock_create:
            mock_create.side_effect = lambda db, batch: batch

            create_batch(db, user_id=uuid.uuid4(), assignor_id=assignor_id, receivable_ids=[r1.id, r2.id])

        assert r1.status == "in_batch"
        assert r2.status == "in_batch"
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

        from app.services.pricing_service import PricingResult
        pricing_result = PricingResult(
            face_value=Decimal("10000.00"),
            present_value=Decimal("9500.00"),
            term_days=120,
            base_rate_annual=Decimal("0.1375"),
            spread_annual=Decimal("0.025"),
            base_rate_daily=Decimal("0.000355"),
            spread_daily=Decimal("0.000068"),
        )

        with patch("app.services.batch_service.batch_repository.get_by_id", return_value=batch), \
             patch("app.services.batch_service.pricing_service.price_receivable", return_value=pricing_result):
            preview = preview_batch(MagicMock(), batch_id=batch.id)

        assert preview.total_receivables == 2
        assert preview.total_face_value == Decimal("20000.00")
        assert preview.total_present_value == Decimal("19000.00")
        assert len(preview.items) == 2
