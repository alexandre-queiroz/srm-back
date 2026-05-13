from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for use as SQLAlchemy column defaults."""
    return datetime.now(UTC)
