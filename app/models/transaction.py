import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        CheckConstraint("term_days > 0", name="chk_transactions_term_positive"),
        CheckConstraint("present_value > 0", name="chk_transactions_present_value_positive"),
        CheckConstraint(
            """
            (instrument_currency = settlement_currency)
            OR
            (instrument_currency <> settlement_currency
             AND exchange_rate_id IS NOT NULL
             AND exchange_rate_used IS NOT NULL)
            """,
            name="chk_transactions_exchange_rate_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("receivables.id"), nullable=False, unique=True)

    face_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    present_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    spread_used: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    base_rate_used: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)

    instrument_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exchange_rates.id"), nullable=True)
    exchange_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(15, 8), nullable=True)

    liquidated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
