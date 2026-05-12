import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class XmlUpload(Base):
    __tablename__ = "xml_uploads"

    __table_args__ = (
        CheckConstraint("status IN ('processed', 'failed')", name="chk_xml_uploads_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    receivables_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
