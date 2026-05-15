import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.models.associations import batch_items
from app.models.batch import Batch
from app.models.receivable import Receivable
from app.models.transaction import Transaction
from app.repositories import batch_repository, receivable_repository
from app.services import pricing_service
from app.services.exchange_rate_service import ExchangeRateError, StaleRateError, get_current_rate
from app.services.pricing_service import create_batch_strategy


class BatchError(Exception):
    pass


class ConcurrencyError(Exception):
    pass


@dataclass
class PreviewItem:
    receivable_id: uuid.UUID
    invoice_key: str
    installment_number: str
    drawee_id: uuid.UUID
    face_value: Decimal
    currency_code: str
    term_days: int
    present_value: Decimal
    base_rate_annual: Decimal
    spread_annual: Decimal


@dataclass
class BatchPreview:
    batch_id: uuid.UUID | None  # None for simulations (no persisted batch)
    assignor_id: uuid.UUID
    total_receivables: int
    total_face_value: Decimal
    total_present_value: Decimal
    items: list[PreviewItem]


def create_batch(
    db: Session,
    user_id: uuid.UUID,
    assignor_id: uuid.UUID,
    receivable_ids: list[uuid.UUID],
) -> Batch:
    if not receivable_ids:
        raise BatchError("Lote deve conter ao menos um recebível.")

    receivables: list[Receivable] = []
    for rid in receivable_ids:
        r = receivable_repository.get_by_id(db, rid)
        if r is None:
            raise BatchError(f"Recebível {rid} não encontrado.")
        if r.assignor_id != assignor_id:
            raise BatchError(f"Recebível {rid} não pertence ao cedente {assignor_id}.")
        if r.status in ("anticipated", "invalid"):
            raise BatchError(f"Recebível {rid} não pode ser incluído em lote (status={r.status}).")
        receivables.append(r)

    batch = Batch(
        assignor_id=assignor_id,
        user_id=user_id,
        status="pending",
        version=0,
    )
    batch_repository.create(db, batch)

    for r in receivables:
        db.execute(batch_items.insert().values(batch_id=batch.id, receivable_id=r.id))

    db.commit()
    db.refresh(batch)
    return batch


def preview_batch(
    db: Session,
    batch_id: uuid.UUID,
    reference_date=None,
) -> BatchPreview:
    batch = batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise BatchError(f"Lote {batch_id} não encontrado.")
    if batch.status not in ("pending", "queued"):
        raise BatchError(f"Lote em status '{batch.status}' não pode ser simulado.")

    # Fetch FX rate once if any receivable is not in BRL — required for cross-currency totals.
    fx_record = None
    if any(r.currency_code != "BRL" for r in batch.receivables):
        try:
            fx_record = get_current_rate(db)
        except (StaleRateError, ExchangeRateError) as exc:
            raise BatchError(f"Taxa de câmbio indisponível: {exc}") from exc

    items: list[PreviewItem] = []
    # Totals are always accumulated in BRL (functional currency).
    total_face = Decimal("0")
    total_pv = Decimal("0")

    for r in batch.receivables:
        result = pricing_service.price_receivable(
            db=db,
            face_value=r.face_value,
            due_date=r.due_date,
            product_type_id=r.product_type_id,
            reference_date=reference_date,
        )
        # Convert to BRL before accumulating to avoid cross-currency aggregation.
        if r.currency_code != "BRL" and fx_record is not None:
            face_brl = (r.face_value * fx_record.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pv_brl = (result.present_value_raw * fx_record.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            face_brl = r.face_value
            pv_brl = result.present_value

        items.append(
            PreviewItem(
                receivable_id=r.id,
                invoice_key=r.invoice_key,
                installment_number=r.installment_number,
                drawee_id=r.drawee_id,
                face_value=r.face_value,
                currency_code=r.currency_code,
                term_days=result.term_days,
                present_value=result.present_value,
                base_rate_annual=result.base_rate_annual,
                spread_annual=result.spread_annual,
            )
        )
        total_face += face_brl
        total_pv += pv_brl

    return BatchPreview(
        batch_id=batch.id,
        assignor_id=batch.assignor_id,
        total_receivables=len(items),
        total_face_value=total_face,
        total_present_value=total_pv,
        items=items,
    )


def simulate_batch(
    db: Session,
    assignor_id: uuid.UUID,
    receivable_ids: list[uuid.UUID],
    reference_date=None,
) -> BatchPreview:
    if not receivable_ids:
        raise BatchError("Simulação deve conter ao menos um recebível.")

    receivables = []
    for rid in receivable_ids:
        r = receivable_repository.get_by_id(db, rid)
        if r is None:
            raise BatchError(f"Recebível {rid} não encontrado.")
        if r.assignor_id != assignor_id:
            raise BatchError(f"Recebível {rid} não pertence ao cedente {assignor_id}.")
        receivables.append(r)

    # Fetch FX rate once if any receivable is not in BRL — required for cross-currency totals.
    fx_record = None
    if any(r.currency_code != "BRL" for r in receivables):
        try:
            fx_record = get_current_rate(db)
        except (StaleRateError, ExchangeRateError) as exc:
            raise BatchError(f"Taxa de câmbio indisponível: {exc}") from exc

    items: list[PreviewItem] = []
    # Totals are always accumulated in BRL (functional currency).
    total_face = Decimal("0")
    total_pv = Decimal("0")

    batch_strategy = create_batch_strategy(db)

    for r in receivables:
        result = pricing_service.price_receivable(
            db=db,
            face_value=r.face_value,
            due_date=r.due_date,
            product_type_id=r.product_type_id,
            reference_date=reference_date,
            strategy=batch_strategy,
        )
        # Convert to BRL before accumulating to avoid cross-currency aggregation.
        if r.currency_code != "BRL" and fx_record is not None:
            face_brl = (r.face_value * fx_record.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pv_brl = (result.present_value_raw * fx_record.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            face_brl = r.face_value
            pv_brl = result.present_value

        items.append(
            PreviewItem(
                receivable_id=r.id,
                invoice_key=r.invoice_key,
                installment_number=r.installment_number,
                drawee_id=r.drawee_id,
                face_value=r.face_value,
                currency_code=r.currency_code,
                term_days=result.term_days,
                present_value=result.present_value,
                base_rate_annual=result.base_rate_annual,
                spread_annual=result.spread_annual,
            )
        )
        total_face += face_brl
        total_pv += pv_brl

    return BatchPreview(
        batch_id=None,
        assignor_id=assignor_id,
        total_receivables=len(items),
        total_face_value=total_face,
        total_present_value=total_pv,
        items=items,
    )


def confirm_batch(
    db: Session,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    expected_version: int,
    reference_date=None,
) -> Batch:
    batch = batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise BatchError(f"Lote {batch_id} não encontrado.")
    if batch.status not in ("pending", "queued"):
        raise BatchError(f"Lote em status '{batch.status}' não pode ser confirmado.")

    # Fetch FX rate once if any receivable is not in BRL
    fx_record = None
    if any(r.currency_code != "BRL" for r in batch.receivables):
        try:
            fx_record = get_current_rate(db)
        except (StaleRateError, ExchangeRateError) as exc:
            raise BatchError(f"Taxa de câmbio indisponível: {exc}") from exc

    # Pre-fetch base rate once; all receivables in a batch share the same system parameter
    batch_strategy = create_batch_strategy(db)

    # Price all receivables (read-only DB queries) before acquiring the lock
    priced: list[tuple[Receivable, object, Decimal, uuid.UUID | None, Decimal | None]] = []
    for r in batch.receivables:
        result = pricing_service.price_receivable(
            db=db,
            face_value=r.face_value,
            due_date=r.due_date,
            product_type_id=r.product_type_id,
            reference_date=reference_date,
            strategy=batch_strategy,
        )
        if r.currency_code != "BRL" and fx_record is not None:
            # Use present_value_raw (full precision) before multiplying by FX rate
            # to avoid accumulated rounding error in cross-currency settlement.
            pv_settlement = (result.present_value_raw * fx_record.rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            ex_rate_id = fx_record.id
            ex_rate_used = fx_record.rate
        else:
            pv_settlement = result.present_value
            ex_rate_id = None
            ex_rate_used = None
        priced.append((r, result, pv_settlement, ex_rate_id, ex_rate_used))

    # Atomic optimistic lock: update only if version still matches
    update_result = db.execute(
        sa_update(Batch)
        .where(Batch.id == batch_id, Batch.version == expected_version)
        .values(status="approved", version=expected_version + 1, updated_at=datetime.now(UTC))
    )
    if update_result.rowcount == 0:
        raise ConcurrencyError("Lote foi modificado por outro processo. Recarregue e tente novamente.")

    # With the lock held, re-check each receivable (FOR UPDATE) to detect concurrent anticipation
    conflicts: dict[str, str] = {}
    for r, _, _, _, _ in priced:
        locked = db.query(Receivable).filter(Receivable.id == r.id).with_for_update().first()
        if locked is None or locked.status != "available":
            conflicts[str(r.id)] = f"status={locked.status if locked else 'not_found'}"

    if conflicts:
        rejection_reasons = {"conflicts": conflicts, "reason": "receivable_already_anticipated"}
        db.execute(
            sa_update(Batch)
            .where(Batch.id == batch_id)
            .values(
                status="rejected",
                rejection_reasons=rejection_reasons,
                updated_at=datetime.now(UTC),
            )
        )
        batch.status = "rejected"
        batch.rejection_reasons = rejection_reasons
        db.commit()
        db.refresh(batch)
        return batch

    # All receivables still available — build transactions and confirm
    transactions = []
    for r, result, pv_settlement, ex_rate_id, ex_rate_used in priced:
        transactions.append(
            Transaction(
                batch_id=batch.id,
                receivable_id=r.id,
                face_value=r.face_value,
                present_value=pv_settlement,
                term_days=result.term_days,
                spread_used=result.spread_annual,
                base_rate_used=result.base_rate_annual,
                instrument_currency=r.currency_code,
                settlement_currency="BRL",
                exchange_rate_id=ex_rate_id,
                exchange_rate_used=ex_rate_used,
                liquidated_by=user_id,
                liquidated_at=datetime.now(UTC),
            )
        )
        r.status = "anticipated"
    db.add_all(transactions)

    db.commit()
    db.refresh(batch)
    return batch


def queue_batch(db: Session, batch_id: uuid.UUID, expected_version: int) -> Batch:
    batch = batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise BatchError(f"Lote {batch_id} não encontrado.")
    if batch.status != "pending":
        raise BatchError(f"Lote em status '{batch.status}' não pode ser enfileirado.")

    update_result = db.execute(
        sa_update(Batch)
        .where(Batch.id == batch_id, Batch.version == expected_version)
        .values(status="queued", version=expected_version + 1, updated_at=datetime.now(UTC))
    )
    if update_result.rowcount == 0:
        raise ConcurrencyError("Lote foi modificado por outro processo. Recarregue e tente novamente.")

    db.commit()
    db.refresh(batch)
    return batch
