"""extend_user_model

Revision ID: 71599f082b7b
Revises: c3d4e5f6a7b9
Create Date: 2026-07-17 22:17:46.730701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71599f082b7b'
down_revision: Union[str, None] = 'c3d4e5f6a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('must_reset_password', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('must_reset_password')
        batch_op.drop_column('last_login_at')
