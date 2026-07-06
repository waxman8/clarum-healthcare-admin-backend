"""Add enrollment_questionnaires table

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrollment_questionnaires",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("member_id", sa.Integer(), nullable=False, index=True),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("join_reason", sa.String(50), nullable=False),
        sa.Column("has_prior_cover", sa.Boolean(), default=False),
        sa.Column("prior_cover_years", sa.Numeric(5, 2), nullable=True),
        sa.Column("prior_cover_break_days", sa.Integer(), nullable=True),
        sa.Column("prior_cover_proof_type", sa.String(50), nullable=True),
        sa.Column("prior_cover_schemes_json", sa.JSON(), nullable=True),
        sa.Column("is_late_joiner", sa.Boolean(), default=False),
        sa.Column("late_joiner_uncovered_years", sa.Integer(), nullable=True),
        sa.Column("conditions_declared", sa.Boolean(), default=False),
        sa.Column("declared_conditions_json", sa.JSON(), nullable=True),
        sa.Column("completed_by", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("underwriting_decision_id", sa.Integer(), nullable=True),
        sa.Column("engine_outcome", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("enrollment_questionnaires")
