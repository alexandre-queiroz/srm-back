from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.company import Company

batch_items = Table(
    "batch_items",
    Base.metadata,
    Column("batch_id", UUID(as_uuid=True), ForeignKey("batches.id"), primary_key=True),
    Column("receivable_id", UUID(as_uuid=True), ForeignKey("receivables.id"), primary_key=True),
)


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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    assignor: Mapped[Company] = relationship("Company", foreign_keys=[assignor_id], lazy="select")
    receivables = relationship("Receivable", secondary=batch_items, lazy="select")
