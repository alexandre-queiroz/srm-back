from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import batch_items
from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.receivable import Receivable


class Batch(Base):
    __tablename__ = "batches"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'approved', 'rejected')",
            name="chk_batches_status",
        ),
        Index("ix_batches_assignor_id", "assignor_id"),
        Index("ix_batches_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    rejection_reasons: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utcnow)

    assignor: Mapped[Company] = relationship("Company", foreign_keys=[assignor_id], lazy="select")
    receivables: Mapped[list[Receivable]] = relationship(
        "Receivable", secondary=batch_items, back_populates="batches", lazy="select"
    )
