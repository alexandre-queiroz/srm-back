import uuid

from sqlalchemy.orm import Session

from app.models.batch import Batch


def create(db: Session, batch: Batch) -> Batch:
    db.add(batch)
    db.flush()
    return batch


def get_by_id(db: Session, batch_id: uuid.UUID) -> Batch | None:
    return db.query(Batch).filter(Batch.id == batch_id).first()


def list_by_assignor(
    db: Session,
    assignor_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Batch], int]:
    q = db.query(Batch)
    if assignor_id:
        q = q.filter(Batch.assignor_id == assignor_id)
    total = q.count()
    items = q.order_by(Batch.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
