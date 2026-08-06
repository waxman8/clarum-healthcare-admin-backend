"""add_mfa_to_users

Revision ID: a3b4c5d6e7f8
Revises: e4c69f835460
Create Date: 2026-07-30 21:57:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'e4c69f835460'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('totp_secret_enc', sa.String(512), nullable=True))
    op.add_column('users', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('totp_fail_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('totp_lockout_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('recovery_codes_hash', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'recovery_codes_hash')
    op.drop_column('users', 'totp_lockout_until')
    op.drop_column('users', 'totp_fail_count')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret_enc')
