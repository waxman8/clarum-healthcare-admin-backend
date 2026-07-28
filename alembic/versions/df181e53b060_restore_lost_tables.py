"""restore_lost_tables

Revision ID: df181e53b060
Revises: e12f8651d10f
Create Date: 2026-07-28 20:12:55.121270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df181e53b060'
down_revision: Union[str, None] = 'e12f8651d10f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('administrators',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('accreditation_number', sa.String(length=100), nullable=True),
    sa.Column('accreditation_expiry', sa.Date(), nullable=True),
    sa.Column('contact_person', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('physical_address', sa.Text(), nullable=True),
    sa.Column('cms_accreditation_status', sa.String(length=9), nullable=False),
    sa.Column('contract_start_date', sa.Date(), nullable=True),
    sa.Column('contract_end_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_administrators_id'), 'administrators', ['id'], unique=False)
    op.create_index(op.f('ix_administrators_is_deleted'), 'administrators', ['is_deleted'], unique=False)

    op.create_table('broker_appointments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('broker_id', sa.Integer(), nullable=False),
    sa.Column('brokerage_id', sa.Integer(), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=False),
    sa.Column('termination_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=11), nullable=False),
    sa.Column('termination_reason', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_broker_appointments_id'), 'broker_appointments', ['id'], unique=False)
    op.create_index(op.f('ix_broker_appointments_is_deleted'), 'broker_appointments', ['is_deleted'], unique=False)

    op.create_table('broker_commission_scales',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('plan_option_id', sa.Integer(), nullable=True),
    sa.Column('member_type', sa.String(length=17), nullable=False),
    sa.Column('commission_amount_cents', sa.Integer(), nullable=False),
    sa.Column('vat_inclusive', sa.Boolean(), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('regulatory_max_cents', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_broker_commission_scales_id'), 'broker_commission_scales', ['id'], unique=False)

    op.create_table('brokerages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('fsp_number', sa.String(length=50), nullable=False),
    sa.Column('contact_person', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('physical_address', sa.Text(), nullable=True),
    sa.Column('fsp_status', sa.String(length=12), nullable=False),
    sa.Column('fais_category', sa.String(length=100), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_brokerages_id'), 'brokerages', ['id'], unique=False)
    op.create_index(op.f('ix_brokerages_is_deleted'), 'brokerages', ['is_deleted'], unique=False)

    op.create_table('brokers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('brokerage_id', sa.Integer(), nullable=True),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('id_number', sa.String(length=13), nullable=True),
    sa.Column('cms_accreditation_number', sa.String(length=50), nullable=True),
    sa.Column('fais_representative_number', sa.String(length=50), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('cell_number', sa.String(length=20), nullable=True),
    sa.Column('accreditation_status', sa.String(length=12), nullable=False),
    sa.Column('accreditation_expiry', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_brokers_id'), 'brokers', ['id'], unique=False)
    op.create_index(op.f('ix_brokers_is_deleted'), 'brokers', ['is_deleted'], unique=False)

    op.create_table('compliance_officers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('id_number', sa.String(length=13), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('cell_number', sa.String(length=20), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=True),
    sa.Column('term_end_date', sa.Date(), nullable=True),
    sa.Column('qualifications', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_officers_id'), 'compliance_officers', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_officers_is_deleted'), 'compliance_officers', ['is_deleted'], unique=False)

    op.create_table('employer_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('registration_number', sa.String(length=50), nullable=True),
    sa.Column('contact_person', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('physical_address', sa.Text(), nullable=True),
    sa.Column('postal_address', sa.Text(), nullable=True),
    sa.Column('payroll_reference', sa.String(length=100), nullable=True),
    sa.Column('contract_start_date', sa.Date(), nullable=True),
    sa.Column('contract_end_date', sa.Date(), nullable=True),
    sa.Column('employee_count', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_employer_groups_id'), 'employer_groups', ['id'], unique=False)
    op.create_index(op.f('ix_employer_groups_is_deleted'), 'employer_groups', ['is_deleted'], unique=False)

    op.create_table('external_auditors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('firm_name', sa.String(length=255), nullable=False),
    sa.Column('partner_name', sa.String(length=200), nullable=True),
    sa.Column('irba_number', sa.String(length=50), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=True),
    sa.Column('engagement_end_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_external_auditors_id'), 'external_auditors', ['id'], unique=False)
    op.create_index(op.f('ix_external_auditors_is_deleted'), 'external_auditors', ['is_deleted'], unique=False)

    op.create_table('information_officers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('id_number', sa.String(length=13), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('cell_number', sa.String(length=20), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=True),
    sa.Column('regulator_registration_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_information_officers_id'), 'information_officers', ['id'], unique=False)
    op.create_index(op.f('ix_information_officers_is_deleted'), 'information_officers', ['is_deleted'], unique=False)

    op.create_table('managed_care_organisations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('accreditation_number', sa.String(length=100), nullable=True),
    sa.Column('accreditation_expiry', sa.Date(), nullable=True),
    sa.Column('contact_person', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('programme_types', sa.String(length=500), nullable=True),
    sa.Column('accreditation_status', sa.String(length=9), nullable=False),
    sa.Column('contract_start_date', sa.Date(), nullable=True),
    sa.Column('contract_end_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_managed_care_organisations_id'), 'managed_care_organisations', ['id'], unique=False)
    op.create_index(op.f('ix_managed_care_organisations_is_deleted'), 'managed_care_organisations', ['is_deleted'], unique=False)

    op.create_table('member_employer_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('employer_group_id', sa.Integer(), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('employment_status', sa.String(length=30), nullable=False),
    sa.Column('payroll_reference', sa.String(length=100), nullable=True),
    sa.Column('termination_reason', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_member_employer_history_employer_group_id'), 'member_employer_history', ['employer_group_id'], unique=False)
    op.create_index(op.f('ix_member_employer_history_id'), 'member_employer_history', ['id'], unique=False)
    op.create_index(op.f('ix_member_employer_history_is_deleted'), 'member_employer_history', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_member_employer_history_member_id'), 'member_employer_history', ['member_id'], unique=False)

    op.create_table('principal_officers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('id_number', sa.String(length=13), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('cell_number', sa.String(length=20), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=False),
    sa.Column('term_end_date', sa.Date(), nullable=True),
    sa.Column('cms_notification_date', sa.Date(), nullable=True),
    sa.Column('qualifications', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_principal_officers_id'), 'principal_officers', ['id'], unique=False)
    op.create_index(op.f('ix_principal_officers_is_deleted'), 'principal_officers', ['is_deleted'], unique=False)

    op.create_table('statutory_actuaries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('firm_name', sa.String(length=255), nullable=True),
    sa.Column('assa_fellowship_number', sa.String(length=50), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('appointment_date', sa.Date(), nullable=True),
    sa.Column('term_end_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_statutory_actuaries_id'), 'statutory_actuaries', ['id'], unique=False)
    op.create_index(op.f('ix_statutory_actuaries_is_deleted'), 'statutory_actuaries', ['is_deleted'], unique=False)

    op.create_table('trustees',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheme_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('id_number', sa.String(length=13), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('cell_number', sa.String(length=20), nullable=True),
    sa.Column('role_on_board', sa.String(length=16), nullable=False),
    sa.Column('appointment_date', sa.Date(), nullable=False),
    sa.Column('term_end_date', sa.Date(), nullable=True),
    sa.Column('vetting_status', sa.String(length=8), nullable=False),
    sa.Column('vetting_date', sa.Date(), nullable=True),
    sa.Column('conflict_disclosed', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trustees_id'), 'trustees', ['id'], unique=False)
    op.create_index(op.f('ix_trustees_is_deleted'), 'trustees', ['is_deleted'], unique=False)


def downgrade() -> None:
    op.drop_table('trustees')
    op.drop_table('statutory_actuaries')
    op.drop_table('principal_officers')
    op.drop_table('member_employer_history')
    op.drop_table('managed_care_organisations')
    op.drop_table('information_officers')
    op.drop_table('external_auditors')
    op.drop_table('employer_groups')
    op.drop_table('compliance_officers')
    op.drop_table('brokers')
    op.drop_table('brokerages')
    op.drop_table('broker_commission_scales')
    op.drop_table('broker_appointments')
    op.drop_table('administrators')
