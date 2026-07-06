"""Add member_employer_history link table

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-06-18 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "c3d4e5f6a7b9"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "member_employer_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scheme_id", sa.Integer(), nullable=False, index=True),
        sa.Column("member_id", sa.Integer(), nullable=False, index=True),
        sa.Column("employer_group_id", sa.Integer(), nullable=False, index=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("employment_status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("payroll_reference", sa.String(100), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Auditable
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        # SoftDeletable
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("member_employer_history")
