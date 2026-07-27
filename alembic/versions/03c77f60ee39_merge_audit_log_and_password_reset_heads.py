"""Merge audit log and password reset heads

Revision ID: 03c77f60ee39
Revises: 755d1dd2594b, b9c3d4e5f6a
Create Date: 2026-07-27 15:43:52.618080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03c77f60ee39'
down_revision: Union[str, None] = ('755d1dd2594b', 'b9c3d4e5f6a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
