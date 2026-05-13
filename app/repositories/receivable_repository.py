import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.receivable import Receivable


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
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Receivable], int]:
    q = db.query(Receivable).filter(Receivable.status == "available")
    if assignor_id:
        q = q.filter(Receivable.assignor_id == assignor_id)
    total = q.count()
    items = (
        q.options(*_eager()).order_by(Receivable.due_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return items, total


def create(db: Session, receivable: Receivable) -> Receivable:
    db.add(receivable)
    db.flush()
    return receivable
