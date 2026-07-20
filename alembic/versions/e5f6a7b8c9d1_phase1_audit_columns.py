"""Add entity_label/scheme_id to audit_logs and modified_date/modified_user
to providers, claims, authorisations, underwriting_decisions,
enrollment_questionnaires, dependants, member_contributions,
chronic_registrations, disputes

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-07-20 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "e5f6a7b8c9d1"
down_revision = "d4e5f6a7b8c0"
branch_labels = None
depends_on = None

TABLES_WITH_MODIFIED_COLUMNS = [
    "providers",
    "claims",
    "authorisations",
    "underwriting_decisions",
    "enrollment_questionnaires",
    "dependants",
    "member_contributions",
    "chronic_registrations",
    "disputes",
]


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("entity_label", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("scheme_id", sa.Integer(), nullable=True))

    for table in TABLES_WITH_MODIFIED_COLUMNS:
        op.add_column(table, sa.Column("modified_date", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("modified_user", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table in reversed(TABLES_WITH_MODIFIED_COLUMNS):
        op.drop_column(table, "modified_user")
        op.drop_column(table, "modified_date")

    op.drop_column("audit_logs", "scheme_id")
    op.drop_column("audit_logs", "entity_label")
