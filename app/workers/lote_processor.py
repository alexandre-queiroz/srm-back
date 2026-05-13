"""
Batch liquidation worker.

Processes batches in 'queued' status asynchronously, decoupling the
heavy confirm_batch logic from the request/response cycle.

Invocation options:
  - As a one-shot script:   python -m app.workers.lote_processor
  - From a FastAPI background task: BackgroundTasks.add_task(process_queued_batches, db)
  - Via cron / Celery / APScheduler: call process_queued_batches with a DB session
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.batch import Batch
from app.services.batch_service import BatchError, ConcurrencyError, confirm_batch

logger = logging.getLogger(__name__)

# Sentinel user ID for system-initiated liquidations
_SYSTEM_USER_ID_STR = "00000000-0000-0000-0000-000000000000"


def _get_queued_batches(db: Session) -> list[Batch]:
    return db.query(Batch).filter(Batch.status == "queued").order_by(Batch.created_at).all()


def process_queued_batches(db: Session) -> dict:
    """
    Find all queued batches and attempt to confirm each one.

    Returns a summary dict with counts of successes and failures.
    The caller is responsible for providing and closing the DB session.
    """
    import uuid

    system_user = uuid.UUID(_SYSTEM_USER_ID_STR)
    batches = _get_queued_batches(db)

    if not batches:
        logger.info("lote_processor: no queued batches found")
        return {"processed": 0, "failed": 0, "skipped": 0}

    processed = 0
    failed = 0
    skipped = 0

    for batch in batches:
        batch_id = batch.id
        version = batch.version
        logger.info("lote_processor: processing batch %s (version=%d)", batch_id, version)

        try:
            confirm_batch(
                db=db,
                batch_id=batch_id,
                user_id=system_user,
                expected_version=version,
            )
            processed += 1
            logger.info("lote_processor: batch %s confirmed successfully", batch_id)

        except ConcurrencyError:
            # Another process confirmed this batch between our query and the lock
            skipped += 1
            logger.warning("lote_processor: batch %s skipped — version conflict", batch_id)
            db.rollback()

        except (BatchError, Exception) as exc:
            failed += 1
            logger.error("lote_processor: batch %s failed — %s", batch_id, exc)
            db.rollback()

    summary = {"processed": processed, "failed": failed, "skipped": skipped}
    logger.info("lote_processor: run complete %s at %s", summary, datetime.now(UTC).isoformat())
    return summary


def run() -> None:
    """Entry point for script/cron invocation."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db: Session = SessionLocal()
    try:
        summary = process_queued_batches(db)
        print(summary)  # noqa: T201
    finally:
        db.close()


if __name__ == "__main__":
    run()
