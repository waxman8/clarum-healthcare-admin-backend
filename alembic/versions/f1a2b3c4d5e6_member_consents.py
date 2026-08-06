"""Add member consents (POPIA) with reference table and backfill

Revision ID: f1a2b3c4d5e6
Revises: 6dc4976b4d5f
Create Date: 2026-07-29 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "6dc4976b4d5f"
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
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_consent_purposes_code"),
    )
    op.create_index("ix_consent_purposes_code", "consent_purposes", ["code"])

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
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("consented", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("withdrew_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["purpose"], ["consent_purposes.code"]),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("member_id", "purpose", name="uq_member_consent_purpose"),
    )
    op.create_index("ix_member_consents_member_id", "member_consents", ["member_id"])
    op.create_index("ix_member_consents_scheme_id", "member_consents", ["scheme_id"])
    op.create_index("ix_member_consents_purpose", "member_consents", ["purpose"])

    # Backfill: existing Member.popia_consent_date -> GENERAL consent.
    op.execute(
        sa.text(
            """
            INSERT INTO member_consents
                (member_id, scheme_id, purpose, consented, granted_at)
            SELECT id, scheme_id, :purpose, :consented, popia_consent_date
            FROM members
            WHERE popia_consent_date IS NOT NULL
            """
        ).bindparams(purpose="GENERAL", consented=True)
    )


def downgrade() -> None:
    op.drop_index("ix_member_consents_purpose", table_name="member_consents")
    op.drop_index("ix_member_consents_scheme_id", table_name="member_consents")
    op.drop_index("ix_member_consents_member_id", table_name="member_consents")
    op.drop_table("member_consents")
    op.drop_index("ix_consent_purposes_code", table_name="consent_purposes")
    op.drop_table("consent_purposes")
