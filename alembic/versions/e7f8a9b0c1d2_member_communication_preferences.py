"""Add member communication preferences

Revision ID: e7f8a9b0c1d2
Revises: c3d4e5f6a7b9
Create Date: 2026-07-20 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "member_communication_prefs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("is_opted_in", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint("member_id", "channel", "category", name="uq_member_comm_pref"),
    )
    op.create_index("ix_member_communication_prefs_member_id", "member_communication_prefs", ["member_id"])
    op.create_index("ix_member_communication_prefs_scheme_id", "member_communication_prefs", ["scheme_id"])


def downgrade() -> None:
    op.drop_index("ix_member_communication_prefs_scheme_id", table_name="member_communication_prefs")
    op.drop_index("ix_member_communication_prefs_member_id", table_name="member_communication_prefs")
    op.drop_table("member_communication_prefs")
