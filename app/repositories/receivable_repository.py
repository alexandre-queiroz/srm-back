import uuid
from datetime import date

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.receivable import Receivable
from app.repositories._filters import str_filter
from app.repositories.cursor import decode_cursor, encode_cursor


def _eager() -> list:
    return [
        joinedload(Receivable.assignor),
        joinedload(Receivable.drawee),
        joinedload(Receivable.product_type),
    ]


def get_by_id(db: Session, receivable_id: uuid.UUID, for_update: bool = False) -> Receivable | None:
    q = db.query(Receivable).filter(Receivable.id == receivable_id)
    if for_update:
        q = q.with_for_update()
    return q.first()


def get_by_invoice_installment(db: Session, invoice_key: str, installment_number: str) -> Receivable | None:
    return (
        db.query(Receivable)
        .filter(
            Receivable.invoice_key == invoice_key,
            Receivable.installment_number == installment_number,
        )
        .first()
    )


def list_available(
    db: Session,
    assignor_id: uuid.UUID | None = None,
    drawee_id: uuid.UUID | None = None,
    status: str | None = None,
    invoice_key: str | None = None,
    invoice_key_op: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Receivable], int]:
    q = db.query(Receivable)
    if status:
        q = q.filter(Receivable.status == status)
    elif not any([assignor_id, drawee_id, invoice_key]):
        # Default to available if no specific filter is provided to avoid leaking all titles
        q = q.filter(Receivable.status == "available")

    if assignor_id:
        q = q.filter(Receivable.assignor_id == assignor_id)
    if drawee_id:
        q = q.filter(Receivable.drawee_id == drawee_id)
    if invoice_key:
        q = q.filter(str_filter(Receivable.invoice_key, invoice_key, invoice_key_op))

    total = q.count()
    items = (
        q.options(*_eager()).order_by(Receivable.due_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return items, total


def list_available_cursor(
    db: Session,
    assignor_id: uuid.UUID | None = None,
    drawee_id: uuid.UUID | None = None,
    status: str | None = None,
    invoice_key: str | None = None,
    invoice_key_op: str | None = None,
    after: str | None = None,
    page_size: int = 20,
) -> tuple[list[Receivable], str | None]:
    """
    Keyset pagination sorted by (due_date ASC, id ASC).
    """
    q = db.query(Receivable)
    if status:
        q = q.filter(Receivable.status == status)
    elif not any([assignor_id, drawee_id, invoice_key]):
        q = q.filter(Receivable.status == "available")

    if assignor_id:
        q = q.filter(Receivable.assignor_id == assignor_id)
    if drawee_id:
        q = q.filter(Receivable.drawee_id == drawee_id)
    if invoice_key:
        q = q.filter(str_filter(Receivable.invoice_key, invoice_key, invoice_key_op))

    if after:
        raw = decode_cursor(after)
        cursor_date = date.fromisoformat(raw[0])
        cursor_id = uuid.UUID(raw[1])
        # Rows where (due_date > cursor_date) OR (due_date == cursor_date AND id > cursor_id)
        q = q.filter(
            or_(
                Receivable.due_date > cursor_date,
                and_(Receivable.due_date == cursor_date, Receivable.id > cursor_id),
            )
        )

    items = (
        q.options(*_eager())
        .order_by(Receivable.due_date.asc(), Receivable.id.asc())
        .limit(page_size + 1)  # fetch one extra to detect if there's a next page
        .all()
    )

    if len(items) > page_size:
        items = items[:page_size]
        last = items[-1]
        next_cursor = encode_cursor(last.due_date, last.id)
    else:
        next_cursor = None

    return items, next_cursor


def create(db: Session, receivable: Receivable) -> Receivable:
    db.add(receivable)
    db.flush()
    return receivable
