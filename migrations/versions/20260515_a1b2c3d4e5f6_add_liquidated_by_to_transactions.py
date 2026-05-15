"""add liquidated_by to transactions

Revision ID: a1b2c3d4e5f6
Revises: d440e2d85f3b
Create Date: 2026-05-15 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d440e2d85f3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No FK constraint: allows the system worker sentinel UUID
    # (00000000-0000-0000-0000-000000000000) without requiring a users row.
    op.add_column(
        "transactions",
        sa.Column(
            "liquidated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who triggered the liquidation. NULL = system worker.",
        ),
    )
    op.create_index("ix_transactions_liquidated_by", "transactions", ["liquidated_by"])


def downgrade() -> None:
    op.drop_index("ix_transactions_liquidated_by", table_name="transactions")
    op.drop_column("transactions", "liquidated_by")
