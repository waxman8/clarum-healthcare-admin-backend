"""Add POPIA consent_purposes reference table and member_consents history table

Revision ID: f8a9b0c1d2e3
Revises: e5f6a7b8c9d1
Create Date: 2026-07-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "f8a9b0c1d2e3"
down_revision = "e5f6a7b8c9d1"
branch_labels = None
depends_on = None


CONSENT_PURPOSES = [
    ("GENERAL", "General processing of personal information for scheme administration"),
    ("MARKETING", "Marketing and member communications"),
    ("SHARE_WITH_ADMIN", "Sharing data with the scheme's administrator"),
    ("SHARE_WITH_REINSURER", "Sharing data with reinsurers"),
    ("MEDICAL_HISTORY_ANALYTICS", "Use of medical history for analytics"),
    ("THIRD_PARTY_RESEARCH", "Sharing data with third parties for research"),
]


def upgrade() -> None:
    op.create_table(
        "consent_purposes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index(op.f("ix_consent_purposes_code"), "consent_purposes", ["code"], unique=True)

    consent_purposes_table = sa.table(
        "consent_purposes",
        sa.column("code", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        consent_purposes_table,
        [{"code": code, "description": description, "is_active": True} for code, description in CONSENT_PURPOSES],
    )

    op.create_table(
        "member_consents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scheme_id", sa.Integer(), nullable=False, index=True),
        sa.Column("member_id", sa.Integer(), nullable=False, index=True),
        sa.Column("purpose", sa.String(50), nullable=False, index=True),
        sa.Column("consented", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("withdrew_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("member_id", "purpose", "version", name="uq_member_consent_version"),
    )

    # Data migration: backfill existing Member.popia_consent_date into a GENERAL consent row.
    # Members with no popia_consent_date get no row (shown as "not recorded", not "withdrawn").
    op.execute(
        """
        INSERT INTO member_consents (scheme_id, member_id, purpose, consented, version, granted_at, created_at)
        SELECT scheme_id, id, 'GENERAL', 1, 1, popia_consent_date, popia_consent_date
        FROM members
        WHERE popia_consent_date IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("member_consents")
    op.drop_index(op.f("ix_consent_purposes_code"), table_name="consent_purposes")
    op.drop_table("consent_purposes")
