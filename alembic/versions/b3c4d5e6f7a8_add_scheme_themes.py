"""add_scheme_themes

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-31

Creates the scheme_themes table for per-scheme UI branding.
This table was defined in the SchemeTheme model but was never included
in any prior migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheme_themes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id"), nullable=False),
        sa.Column("palette", sa.String(50), nullable=False, server_default="sapphire"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_id"),
    )
    op.create_index("ix_scheme_themes_scheme_id", "scheme_themes", ["scheme_id"])


def downgrade() -> None:
    op.drop_index("ix_scheme_themes_scheme_id", table_name="scheme_themes")
    op.drop_table("scheme_themes")
