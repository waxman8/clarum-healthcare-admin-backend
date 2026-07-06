"""Week-1 sprint: employer groups + intermediaries (brokers)

Adds 5 tables: employer_groups, brokerages, brokers,
broker_commission_scales, broker_appointments.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def _mixin_columns_mtas():
    """MultiTenant + Auditable + SoftDeletable"""
    return [
        sa.Column("scheme_id", sa.Integer(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
    ]


def _mixin_columns_mta():
    """MultiTenant + Auditable (no SoftDeletable)"""
    return [
        sa.Column("scheme_id", sa.Integer(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    ]


def upgrade() -> None:
    # 1. Employer Groups
    op.create_table(
        "employer_groups",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("registration_number", sa.String(50), nullable=True),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("physical_address", sa.Text(), nullable=True),
        sa.Column("postal_address", sa.Text(), nullable=True),
        sa.Column("payroll_reference", sa.String(100), nullable=True),
        sa.Column("contract_start_date", sa.Date(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns_mtas(),
    )

    # 2. Brokerages (FSP)
    op.create_table(
        "brokerages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("fsp_number", sa.String(50), nullable=False),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("physical_address", sa.Text(), nullable=True),
        sa.Column("fsp_status", sa.String(12), nullable=False, server_default="ACTIVE"),
        sa.Column("fais_category", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns_mtas(),
    )

    # 3. Brokers (individual representatives)
    op.create_table(
        "brokers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("brokerage_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(13), nullable=True),
        sa.Column("cms_accreditation_number", sa.String(50), nullable=True),
        sa.Column("fais_representative_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cell_number", sa.String(20), nullable=True),
        sa.Column("accreditation_status", sa.String(12), nullable=False, server_default="ACTIVE"),
        sa.Column("accreditation_expiry", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns_mtas(),
    )

    # 4. Broker Commission Scales (reference data — no SoftDeletable)
    op.create_table(
        "broker_commission_scales",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("plan_option_id", sa.Integer(), nullable=True),
        sa.Column("member_type", sa.String(17), nullable=False),
        sa.Column("commission_amount_cents", sa.Integer(), nullable=False),
        sa.Column("vat_inclusive", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("regulatory_max_cents", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns_mta(),
    )

    # 5. Broker Appointments (member-broker link)
    op.create_table(
        "broker_appointments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("brokerage_id", sa.Integer(), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(11), nullable=False, server_default="ACTIVE"),
        sa.Column("termination_reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_mixin_columns_mtas(),
    )


def downgrade() -> None:
    op.drop_table("broker_appointments")
    op.drop_table("broker_commission_scales")
    op.drop_table("brokers")
    op.drop_table("brokerages")
    op.drop_table("employer_groups")
