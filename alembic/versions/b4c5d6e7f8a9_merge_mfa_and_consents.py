"""merge mfa and consents heads

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8, f1a2b3c4d5e6
Create Date: 2026-08-03 11:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = ('a3b4c5d6e7f8', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
