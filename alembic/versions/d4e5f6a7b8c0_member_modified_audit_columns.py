"""Add modified_date and modified_user audit columns to members

Revision ID: d4e5f6a7b8c0
Revises: f7a8b9c0d1e2
Create Date: 2026-07-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "d4e5f6a7b8c0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("members", sa.Column("modified_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("members", sa.Column("modified_user", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "modified_user")
    op.drop_column("members", "modified_date")
