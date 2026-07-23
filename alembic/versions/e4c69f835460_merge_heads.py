"""merge heads

Revision ID: e4c69f835460
Revises: 71599f082b7b, e7f8a9b0c1d2
Create Date: 2026-07-24 00:34:22.839487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4c69f835460'
down_revision: Union[str, None] = ('71599f082b7b', 'e7f8a9b0c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
