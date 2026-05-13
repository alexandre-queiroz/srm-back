import uuid
from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.batch import Batch
from app.repositories.cursor import decode_cursor, encode_cursor


def _eager() -> list:
    return [joinedload(Batch.assignor)]


def create(db: Session, batch: Batch) -> Batch:
    db.add(batch)
    db.flush()
    return batch


def get_by_id(db: Session, batch_id: uuid.UUID) -> Batch | None:
    return db.query(Batch).options(*_eager()).filter(Batch.id == batch_id).first()


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
    items = q.options(*_eager()).order_by(Batch.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def list_by_assignor_cursor(
    db: Session,
    assignor_id: uuid.UUID | None = None,
    after: str | None = None,
    page_size: int = 20,
) -> tuple[list[Batch], str | None]:
    """
    Keyset pagination sorted by (created_at DESC, id DESC).

    Returns (items, next_cursor). Pass next_cursor as ``after`` to fetch the
    next page. When next_cursor is None you have reached the last page.
    O(K) at any depth — no OFFSET scan.
    """
    q = db.query(Batch)
    if assignor_id:
        q = q.filter(Batch.assignor_id == assignor_id)

    if after:
        raw = decode_cursor(after)
        cursor_ts = datetime.fromisoformat(raw[0])
        cursor_id = uuid.UUID(raw[1])
        # Rows where (created_at < cursor_ts) OR (created_at == cursor_ts AND id < cursor_id)
        q = q.filter(
            or_(
                Batch.created_at < cursor_ts,
                and_(Batch.created_at == cursor_ts, Batch.id < cursor_id),
            )
        )

    items = q.options(*_eager()).order_by(Batch.created_at.desc(), Batch.id.desc()).limit(page_size + 1).all()

    if len(items) > page_size:
        items = items[:page_size]
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    else:
        next_cursor = None

    return items, next_cursor
