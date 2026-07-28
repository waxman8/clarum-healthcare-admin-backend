"""merge multiple heads

Revision ID: 2aabc727827d
Revises: 03c77f60ee39, 6dc4976b4d5f
Create Date: 2026-07-28 17:09:02.414258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2aabc727827d'
down_revision: Union[str, None] = ('03c77f60ee39', '6dc4976b4d5f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
