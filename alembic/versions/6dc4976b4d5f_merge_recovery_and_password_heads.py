"""merge recovery and password heads

Revision ID: 6dc4976b4d5f
Revises: 82c1a3b7e9d0, b9c3d4e5f6a
Create Date: 2026-07-27 22:38:34.876124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6dc4976b4d5f'
down_revision: Union[str, None] = ('82c1a3b7e9d0', 'b9c3d4e5f6a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
