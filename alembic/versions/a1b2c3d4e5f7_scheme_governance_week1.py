"""Week-1 sprint: scheme governance entities

Adds 8 tables: trustees, principal_officers, administrators,
managed_care_organisations, external_auditors, statutory_actuaries,
compliance_officers, information_officers.

All include MultiTenant (scheme_id), Auditable (created/updated timestamps
+ created_by/updated_by), and SoftDeletable (is_deleted, deleted_at, deleted_by)
mixin columns.

Revision ID: a1b2c3d4e5f7
Revises: f7a8b9c0d1e2
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


# Common mixin columns shared by all 8 tables
def _mixin_columns():
    return [
        # MultiTenant
        sa.Column("scheme_id", sa.Integer(), nullable=False, index=True),
        # Auditable
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        # SoftDeletable
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
    ]


def upgrade() -> None:
    # 1. Trustees
    op.create_table(
        "trustees",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(13), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cell_number", sa.String(20), nullable=True),
        sa.Column("role_on_board", sa.String(16), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("term_end_date", sa.Date(), nullable=True),
        sa.Column("vetting_status", sa.String(8), nullable=False, server_default="PENDING"),
        sa.Column("vetting_date", sa.Date(), nullable=True),
        sa.Column("conflict_disclosed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 2. Principal Officers
    op.create_table(
        "principal_officers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(13), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cell_number", sa.String(20), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("term_end_date", sa.Date(), nullable=True),
        sa.Column("cms_notification_date", sa.Date(), nullable=True),
        sa.Column("qualifications", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 3. Administrators
    op.create_table(
        "administrators",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("accreditation_number", sa.String(100), nullable=True),
        sa.Column("accreditation_expiry", sa.Date(), nullable=True),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("physical_address", sa.Text(), nullable=True),
        sa.Column("cms_accreditation_status", sa.String(9), nullable=False, server_default="ACTIVE"),
        sa.Column("contract_start_date", sa.Date(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 4. Managed Care Organisations
    op.create_table(
        "managed_care_organisations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("accreditation_number", sa.String(100), nullable=True),
        sa.Column("accreditation_expiry", sa.Date(), nullable=True),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("programme_types", sa.String(500), nullable=True),
        sa.Column("accreditation_status", sa.String(9), nullable=False, server_default="ACTIVE"),
        sa.Column("contract_start_date", sa.Date(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 5. External Auditors
    op.create_table(
        "external_auditors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("firm_name", sa.String(255), nullable=False),
        sa.Column("partner_name", sa.String(200), nullable=True),
        sa.Column("irba_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("engagement_end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 6. Statutory Actuaries
    op.create_table(
        "statutory_actuaries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("firm_name", sa.String(255), nullable=True),
        sa.Column("assa_fellowship_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("term_end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 7. Compliance Officers
    op.create_table(
        "compliance_officers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(13), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cell_number", sa.String(20), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("term_end_date", sa.Date(), nullable=True),
        sa.Column("qualifications", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )

    # 8. Information Officers
    op.create_table(
        "information_officers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(13), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cell_number", sa.String(20), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("regulator_registration_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns(),
    )


def downgrade() -> None:
    op.drop_table("information_officers")
    op.drop_table("compliance_officers")
    op.drop_table("statutory_actuaries")
    op.drop_table("external_auditors")
    op.drop_table("managed_care_organisations")
    op.drop_table("administrators")
    op.drop_table("principal_officers")
    op.drop_table("trustees")
