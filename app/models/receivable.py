from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy import ForeignKey as FK
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import batch_items
from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.company import Company
    from app.models.product_type import ProductType


class Receivable(Base):
    __tablename__ = "receivables"

    __table_args__ = (
        UniqueConstraint("invoice_key", "installment_number", name="uq_receivables_installment"),
        CheckConstraint(
            "status IN ('available', 'anticipated', 'invalid')",
            name="chk_receivables_status",
        ),
        CheckConstraint("face_value > 0", name="chk_receivables_face_value_positive"),
        CheckConstraint("assignor_id <> drawee_id", name="chk_receivables_assignor_drawee_different"),
        Index("ix_receivables_assignor_id", "assignor_id"),
        Index("ix_receivables_status", "status"),
        Index("ix_receivables_due_date", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    xml_upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assignor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), FK("companies.id"), nullable=False)
    drawee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), FK("companies.id"), nullable=False)
    product_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), FK("product_types.id"), nullable=False)

    invoice_key: Mapped[str] = mapped_column(String(44), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(9), nullable=False)
    series: Mapped[str] = mapped_column(String(3), nullable=False)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    installment_number: Mapped[str] = mapped_column(String(60), nullable=False)

    products_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal("0"))
    freight_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal("0"))
    other_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal("0"))
    face_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    xml_storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utcnow)

    assignor: Mapped[Company] = relationship("Company", foreign_keys=[assignor_id], lazy="select")
    drawee: Mapped[Company] = relationship("Company", foreign_keys=[drawee_id], lazy="select")
    product_type: Mapped[ProductType] = relationship("ProductType", lazy="select")
    batches: Mapped[list[Batch]] = relationship(
        "Batch", secondary=batch_items, back_populates="receivables", lazy="select"
    )
