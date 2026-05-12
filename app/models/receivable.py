import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Receivable(Base):
    __tablename__ = "receivables"

    __table_args__ = (
        UniqueConstraint("invoice_key", "installment_number", name="uq_receivables_installment"),
        CheckConstraint("status IN ('available', 'in_batch', 'anticipated')", name="chk_receivables_status"),
        CheckConstraint("face_value > 0", name="chk_receivables_face_value_positive"),
        CheckConstraint("assignor_id <> drawee_id", name="chk_receivables_assignor_drawee_different"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    drawee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
