"""remove_in_batch_status_allow_multi_batch

A receivable can now belong to multiple pending batches simultaneously.
The worker is responsible for rejecting a batch if any of its receivables
was already anticipated by another batch that was confirmed first.

Revision ID: b1c4d9e7f823
Revises: 79be00a733d1
Create Date: 2026-05-13 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4d9e7f823"
down_revision: Union[str, None] = "79be00a733d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Roll back any receivables stuck in in_batch before dropping the constraint
    op.execute("UPDATE receivables SET status = 'available' WHERE status = 'in_batch'")

    op.drop_constraint("chk_receivables_status", "receivables", type_="check")
    op.create_check_constraint(
        "chk_receivables_status",
        "receivables",
        "status IN ('available', 'anticipated', 'invalid')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_receivables_status", "receivables", type_="check")
    op.create_check_constraint(
        "chk_receivables_status",
        "receivables",
        "status IN ('available', 'in_batch', 'anticipated', 'invalid')",
    )
