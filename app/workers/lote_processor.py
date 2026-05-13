"""
Batch liquidation worker.

Processes batches in 'queued' status asynchronously, decoupling the
heavy confirm_batch logic from the request/response cycle.
"""

import logging
import signal
import sys
import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.observability import close_observability, setup_observability
from app.models.batch import Batch
from app.services.batch_service import BatchError, ConcurrencyError, confirm_batch

logger = logging.getLogger(__name__)

# Sentinel user ID for system-initiated liquidations
_SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# Graceful shutdown flag
should_exit = False


def handle_signal(signum, frame):
    global should_exit
    logger.info("Signal %d received, shutting down gracefully...", signum)
    should_exit = True


def _get_queued_batches(db: Session) -> list[Batch]:
    return db.query(Batch).filter(Batch.status == "queued").order_by(Batch.created_at).all()


def process_queued_batches(db: Session) -> dict:
    """
    Find all queued batches and attempt to confirm each one.
    """
    batches = _get_queued_batches(db)

    if not batches:
        return {"processed": 0, "failed": 0, "skipped": 0}

    processed = 0
    failed = 0
    skipped = 0

    for batch in batches:
        if should_exit:
            break

        batch_id = batch.id
        version = batch.version
        logger.info("Processing batch %s (version=%d)", batch_id, version)

        try:
            confirm_batch(
                db=db,
                batch_id=batch_id,
                user_id=_SYSTEM_USER_ID,
                expected_version=version,
            )
            processed += 1
            logger.info("Batch %s confirmed successfully", batch_id)
        except ConcurrencyError:
            skipped += 1
            logger.warning("Batch %s skipped — version conflict", batch_id)
            db.rollback()
        except (BatchError, Exception) as exc:
            failed += 1
            logger.error("Batch %s failed — %s", batch_id, exc)
            db.rollback()

    return {"processed": processed, "failed": failed, "skipped": skipped}


def run() -> None:
    """Persistent worker loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    setup_observability()

    poll_interval = settings.WORKER_POLL_INTERVAL
    logger.info("Worker started. Poll interval: %ds", poll_interval)

    while not should_exit:
        db: Session = SessionLocal()
        try:
            summary = process_queued_batches(db)
            if summary["processed"] > 0 or summary["failed"] > 0:
                logger.info("Run summary: %s", summary)
        except Exception as e:
            logger.error("Unexpected error in worker loop: %s", e)
        finally:
            db.close()

        # Sleep in small increments to remain responsive to signals
        for _ in range(poll_interval):
            if should_exit:
                break
            time.sleep(1)

    close_observability()
    logger.info("Worker stopped.")


if __name__ == "__main__":
    run()
