"""
Association tables for many-to-many relationships.

Isolated here to break circular imports between models that need to reference
each other via back_populates.
"""

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

batch_items = Table(
    "batch_items",
    Base.metadata,
    Column("batch_id", UUID(as_uuid=True), ForeignKey("batches.id"), primary_key=True),
    Column("receivable_id", UUID(as_uuid=True), ForeignKey("receivables.id"), primary_key=True),
)
