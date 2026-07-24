"""add recovery cases

Revision ID: 82c1a3b7e9d0
Revises: 71599f082b7b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "82c1a3b7e9d0"
down_revision: Union[str, None] = "71599f082b7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("recovery_type", sa.String(length=20), nullable=False),
        sa.Column("third_party_name", sa.String(length=255), nullable=False),
        sa.Column("third_party_reference", sa.String(length=100)),
        sa.Column("expected_cents", sa.Integer(), nullable=False),
        sa.Column("recovered_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True)),
        sa.Column("status_changed_by", sa.Integer()),
        sa.Column("status_reason", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer()),
        sa.Column("updated_by", sa.Integer()),
    )
    op.create_index("ix_recovery_cases_scheme_id", "recovery_cases", ["scheme_id"])
    op.create_index("ix_recovery_cases_recovery_type", "recovery_cases", ["recovery_type"])
    op.create_table(
        "recovery_case_claim_links",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("recovery_case_id", sa.Integer(), nullable=False), sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("allocation_cents", sa.Integer(), nullable=False), sa.Column("recovered_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer()), sa.Column("updated_by", sa.Integer()),
    )
    op.create_index("ix_recovery_case_claim_links_scheme_id", "recovery_case_claim_links", ["scheme_id"])
    op.create_index("ix_recovery_case_claim_links_recovery_case_id", "recovery_case_claim_links", ["recovery_case_id"])
    op.create_index("ix_recovery_case_claim_links_claim_id", "recovery_case_claim_links", ["claim_id"])
    op.create_table(
        "recovery_receipts",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("recovery_case_id", sa.Integer(), nullable=False), sa.Column("amount_cents", sa.Integer(), nullable=False), sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer()), sa.Column("updated_by", sa.Integer()),
    )
    op.create_index("ix_recovery_receipts_scheme_id", "recovery_receipts", ["scheme_id"])
    op.create_index("ix_recovery_receipts_recovery_case_id", "recovery_receipts", ["recovery_case_id"])
    with op.batch_alter_table("claims") as batch_op:
        batch_op.add_column(sa.Column("recovered_cents", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("claims") as batch_op:
        batch_op.drop_column("recovered_cents")
    op.drop_table("recovery_receipts")
    op.drop_table("recovery_case_claim_links")
    op.drop_table("recovery_cases")
