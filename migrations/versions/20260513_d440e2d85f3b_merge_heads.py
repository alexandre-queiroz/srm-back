"""merge_heads

Revision ID: d440e2d85f3b
Revises: 242eebdf08c4, d33b210d3994
Create Date: 2026-05-13 21:01:21.183246+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd440e2d85f3b'
down_revision: Union[str, None] = ('242eebdf08c4', 'd33b210d3994')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
