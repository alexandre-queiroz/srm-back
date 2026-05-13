"""add_fks_and_indexes

Adds missing foreign key constraints on receivables and performance indexes
across receivables, batches, and transactions.

Revision ID: d33b210d3994
Revises: 996b88dd4a35
Create Date: 2026-05-13 00:00:00.000000+00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d33b210d3994"
down_revision: str | None = "996b88dd4a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Foreign keys on receivables (were missing — no referential integrity)
    op.create_foreign_key(
        "fk_receivables_assignor_id",
        "receivables",
        "companies",
        ["assignor_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_receivables_drawee_id",
        "receivables",
        "companies",
        ["drawee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_receivables_product_type_id",
        "receivables",
        "product_types",
        ["product_type_id"],
        ["id"],
    )

    # Indexes on receivables for common filter columns
    op.create_index("ix_receivables_assignor_id", "receivables", ["assignor_id"])
    op.create_index("ix_receivables_status", "receivables", ["status"])
    op.create_index("ix_receivables_due_date", "receivables", ["due_date"])

    # Indexes on batches
    op.create_index("ix_batches_assignor_id", "batches", ["assignor_id"])
    op.create_index("ix_batches_status", "batches", ["status"])

    # Indexes on transactions for reporting queries
    op.create_index("ix_transactions_batch_id", "transactions", ["batch_id"])
    op.create_index("ix_transactions_liquidated_at", "transactions", ["liquidated_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_liquidated_at", "transactions")
    op.drop_index("ix_transactions_batch_id", "transactions")

    op.drop_index("ix_batches_status", "batches")
    op.drop_index("ix_batches_assignor_id", "batches")

    op.drop_index("ix_receivables_due_date", "receivables")
    op.drop_index("ix_receivables_status", "receivables")
    op.drop_index("ix_receivables_assignor_id", "receivables")

    op.drop_constraint("fk_receivables_product_type_id", "receivables", type_="foreignkey")
    op.drop_constraint("fk_receivables_drawee_id", "receivables", type_="foreignkey")
    op.drop_constraint("fk_receivables_assignor_id", "receivables", type_="foreignkey")
