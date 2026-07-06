"""healthcare_enterprise_extensions

Revision ID: a2b3c4d5e6f7
Revises: f113a87be4fa
Create Date: 2026-05-31

Adds:
- New columns on plan_options, icd10_codes, tariff_codes, members, dependants,
  claim_lines, audit_logs, providers
- New tables: nappi_codes, contribution_rates, benefit_balances, savings_accounts,
  copayment_rules, provider_networks, formulary, chronic_registrations,
  claim_adjudication_logs, disputes

All new columns use nullable=True or server_default so existing rows
are unaffected by the migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f113a87be4fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend existing tables — all nullable so existing rows unaffected
    # ------------------------------------------------------------------

    # plan_options
    op.add_column('plan_options', sa.Column('hospital_network', sa.String(20), nullable=True))
    op.add_column('plan_options', sa.Column('day_to_day_type', sa.String(20), nullable=True))
    op.add_column('plan_options', sa.Column('care_coordination_required',
                                             sa.Boolean(), nullable=True,
                                             server_default=sa.false()))
    op.add_column('plan_options', sa.Column('gp_referral_required',
                                             sa.Boolean(), nullable=True,
                                             server_default=sa.false()))
    op.add_column('plan_options', sa.Column('benefit_year', sa.Integer(), nullable=True))
    op.add_column('plan_options', sa.Column('tariff_multiplier',
                                             sa.Integer(), nullable=True,
                                             server_default='100'))

    # icd10_codes
    op.add_column('icd10_codes', sa.Column('is_cdl', sa.Boolean(), nullable=True,
                                            server_default=sa.false()))
    op.add_column('icd10_codes', sa.Column('cdl_condition_name', sa.String(200), nullable=True))
    op.add_column('icd10_codes', sa.Column('gender_restriction', sa.String(10), nullable=True))
    op.add_column('icd10_codes', sa.Column('is_billable', sa.Boolean(), nullable=True,
                                            server_default=sa.true()))

    # tariff_codes
    op.add_column('tariff_codes', sa.Column('tariff_list', sa.String(30), nullable=True))
    op.add_column('tariff_codes', sa.Column('discipline_codes', sa.Text(), nullable=True))
    op.add_column('tariff_codes', sa.Column('requires_auth', sa.Boolean(), nullable=True,
                                             server_default=sa.false()))
    op.add_column('tariff_codes', sa.Column('effective_year', sa.Integer(), nullable=True))

    # members
    op.add_column('members', sa.Column('passport_number', sa.String(50), nullable=True))
    op.add_column('members', sa.Column('physical_address', sa.Text(), nullable=True))
    op.add_column('members', sa.Column('termination_reason', sa.String(200), nullable=True))
    op.add_column('members', sa.Column('waiting_period_end_date', sa.Date(), nullable=True))
    op.add_column('members', sa.Column('late_joiner_penalty', sa.Boolean(), nullable=True,
                                        server_default=sa.false()))
    op.add_column('members', sa.Column('popia_consent_date', sa.Date(), nullable=True))
    # Note: id_number remains NOT NULL in the DB (SQLite does not support ALTER COLUMN).
    # Non-SA citizens must still supply id_number="PASSPORT" or a placeholder;
    # passport_number holds their actual travel document number.

    # dependants
    op.add_column('dependants', sa.Column('effective_from', sa.Date(), nullable=True))
    op.add_column('dependants', sa.Column('effective_to', sa.Date(), nullable=True))

    # claim_lines
    op.add_column('claim_lines', sa.Column('nappi_code_id', sa.Integer(), nullable=True))
    op.add_column('claim_lines', sa.Column('benefit_bucket', sa.String(30), nullable=True))
    op.add_column('claim_lines', sa.Column('copayment_cents', sa.Integer(), nullable=True,
                                            server_default='0'))
    op.add_column('claim_lines', sa.Column('scheme_rate_cents', sa.Integer(), nullable=True))
    op.add_column('claim_lines', sa.Column('is_pmb_override', sa.Boolean(), nullable=True,
                                            server_default=sa.false()))

    # audit_logs
    op.add_column('audit_logs', sa.Column('event_id', sa.String(36), nullable=True))
    op.add_column('audit_logs', sa.Column('user_role', sa.String(50), nullable=True))
    op.add_column('audit_logs', sa.Column('ip_address', sa.String(45), nullable=True))
    op.add_column('audit_logs', sa.Column('is_pmb_override', sa.Boolean(), nullable=True,
                                           server_default=sa.false()))
    op.add_column('audit_logs', sa.Column('claim_rejection_code', sa.String(20), nullable=True))
    op.add_column('audit_logs', sa.Column('reason', sa.String(500), nullable=True))

    # providers
    op.add_column('providers', sa.Column('physical_address', sa.Text(), nullable=True))

    # ------------------------------------------------------------------
    # 2. New tables — dependency order: referenced tables first
    # ------------------------------------------------------------------

    # nappi_codes (referenced by formulary and claim_lines)
    op.create_table(
        'nappi_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nappi_code', sa.String(20), nullable=False),
        sa.Column('product_name', sa.String(500), nullable=False),
        sa.Column('generic_name', sa.String(500), nullable=True),
        sa.Column('dosage_form', sa.String(100), nullable=True),
        sa.Column('strength', sa.String(100), nullable=True),
        sa.Column('schedule', sa.String(10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_nappi_codes_id', 'nappi_codes', ['id'], unique=False)
    op.create_index('ix_nappi_codes_nappi_code', 'nappi_codes', ['nappi_code'], unique=True)

    # contribution_rates
    op.create_table(
        'contribution_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_option_id', sa.Integer(), nullable=False),
        sa.Column('member_type', sa.String(30), nullable=False),
        sa.Column('monthly_rate_cents', sa.Integer(), nullable=False),
        sa.Column('effective_year', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['plan_option_id'], ['plan_options.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_option_id', 'member_type', 'effective_year',
                            name='uq_contribution_rate'),
    )
    op.create_index('ix_contribution_rates_id', 'contribution_rates', ['id'], unique=False)
    op.create_index('ix_contribution_rates_plan_option_id', 'contribution_rates',
                    ['plan_option_id'], unique=False)

    # benefit_balances
    op.create_table(
        'benefit_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('benefit_category', sa.String(100), nullable=False),
        sa.Column('benefit_year', sa.Integer(), nullable=False),
        sa.Column('opening_balance_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reserved_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('visits_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('member_id', 'benefit_category', 'benefit_year',
                            name='uq_benefit_balance'),
    )
    op.create_index('ix_benefit_balances_id', 'benefit_balances', ['id'], unique=False)
    op.create_index('ix_benefit_balances_member_id', 'benefit_balances', ['member_id'],
                    unique=False)
    op.create_index('ix_benefit_balances_scheme_id', 'benefit_balances', ['scheme_id'],
                    unique=False)

    # savings_accounts
    op.create_table(
        'savings_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('balance_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ytd_credited_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('benefit_year', sa.Integer(), nullable=False),
        sa.Column('last_credited_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('member_id', name='uq_savings_account_member'),
    )
    op.create_index('ix_savings_accounts_id', 'savings_accounts', ['id'], unique=False)
    op.create_index('ix_savings_accounts_member_id', 'savings_accounts', ['member_id'],
                    unique=True)

    # copayment_rules
    op.create_table(
        'copayment_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('plan_option_id', sa.Integer(), nullable=True),  # NULL = all plans
        sa.Column('trigger', sa.String(100), nullable=False),
        sa.Column('copayment_type', sa.String(20), nullable=False),
        sa.Column('copayment_value', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_upfront', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.ForeignKeyConstraint(['plan_option_id'], ['plan_options.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scheme_id', 'plan_option_id', 'trigger',
                            name='uq_copayment_rule'),
    )
    op.create_index('ix_copayment_rules_id', 'copayment_rules', ['id'], unique=False)
    op.create_index('ix_copayment_rules_scheme_id', 'copayment_rules', ['scheme_id'],
                    unique=False)

    # provider_networks
    op.create_table(
        'provider_networks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('network_type', sa.String(60), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'scheme_id', 'network_type',
                            name='uq_provider_network'),
    )
    op.create_index('ix_provider_networks_id', 'provider_networks', ['id'], unique=False)
    op.create_index('ix_provider_networks_provider_id', 'provider_networks', ['provider_id'],
                    unique=False)
    op.create_index('ix_provider_networks_scheme_id', 'provider_networks', ['scheme_id'],
                    unique=False)

    # formulary (depends on nappi_codes, tariff_codes, plan_options)
    op.create_table(
        'formulary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_option_id', sa.Integer(), nullable=False),
        sa.Column('formulary_type', sa.String(20), nullable=False),
        sa.Column('nappi_code_id', sa.Integer(), nullable=True),
        sa.Column('tariff_code_id', sa.Integer(), nullable=True),
        sa.Column('cdl_condition', sa.String(100), nullable=True),
        sa.Column('is_covered', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('is_preferred', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('reference_price_cents', sa.Integer(), nullable=True),
        sa.Column('max_quantity_per_script', sa.Integer(), nullable=True),
        sa.Column('max_scripts_per_period', sa.Integer(), nullable=True),
        sa.Column('period_days', sa.Integer(), nullable=True),
        sa.Column('copayment_if_non_formulary_pct', sa.Integer(), nullable=True,
                  server_default='20'),
        sa.Column('effective_year', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['plan_option_id'], ['plan_options.id']),
        sa.ForeignKeyConstraint(['nappi_code_id'], ['nappi_codes.id']),
        sa.ForeignKeyConstraint(['tariff_code_id'], ['tariff_codes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_formulary_id', 'formulary', ['id'], unique=False)
    op.create_index('ix_formulary_plan_option_id', 'formulary', ['plan_option_id'],
                    unique=False)

    # chronic_registrations (depends on members, dependants, icd10_codes, users)
    op.create_table(
        'chronic_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('dependant_id', sa.Integer(), nullable=True),
        sa.Column('icd10_code_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('application_date', sa.Date(), nullable=False),
        sa.Column('decision_date', sa.Date(), nullable=True),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('approved_medicines', sa.Text(), nullable=True),
        sa.Column('care_plan', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_pmb', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['dependant_id'], ['dependants.id']),
        sa.ForeignKeyConstraint(['icd10_code_id'], ['icd10_codes.id']),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chronic_registrations_id', 'chronic_registrations', ['id'],
                    unique=False)
    op.create_index('ix_chronic_registrations_member_id', 'chronic_registrations',
                    ['member_id'], unique=False)
    op.create_index('ix_chronic_registrations_scheme_id', 'chronic_registrations',
                    ['scheme_id'], unique=False)

    # claim_adjudication_logs (depends on claims, claim_lines)
    op.create_table(
        'claim_adjudication_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('claim_line_id', sa.Integer(), nullable=True),
        sa.Column('stage', sa.Integer(), nullable=False),
        sa.Column('stage_name', sa.String(50), nullable=False),
        sa.Column('rule_code', sa.String(20), nullable=False),
        sa.Column('result', sa.String(20), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.ForeignKeyConstraint(['claim_line_id'], ['claim_lines.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_claim_adjudication_logs_id', 'claim_adjudication_logs', ['id'],
                    unique=False)
    op.create_index('ix_claim_adjudication_logs_claim_id', 'claim_adjudication_logs',
                    ['claim_id'], unique=False)

    # disputes (depends on schemes, members, claims, users)
    op.create_table(
        'disputes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('dispute_number', sa.String(50), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=True),
        sa.Column('dispute_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('date_received', sa.Date(), nullable=False),
        sa.Column('member_deadline', sa.Date(), nullable=False),
        sa.Column('admin_deadline', sa.Date(), nullable=False),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('escalated_to_cms', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('cms_reference', sa.String(100), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scheme_id'], ['schemes.id']),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dispute_number', name='uq_dispute_number'),
    )
    op.create_index('ix_disputes_id', 'disputes', ['id'], unique=False)
    op.create_index('ix_disputes_dispute_number', 'disputes', ['dispute_number'], unique=True)
    op.create_index('ix_disputes_member_id', 'disputes', ['member_id'], unique=False)
    op.create_index('ix_disputes_scheme_id', 'disputes', ['scheme_id'], unique=False)

    # Note: FK for claim_lines.nappi_code_id is enforced by SQLAlchemy ORM relationships.
    # SQLite does not support adding FK constraints via ALTER TABLE.


def downgrade() -> None:
    # Drop new tables in reverse dependency order
    op.drop_index('ix_disputes_scheme_id', table_name='disputes')
    op.drop_index('ix_disputes_member_id', table_name='disputes')
    op.drop_index('ix_disputes_dispute_number', table_name='disputes')
    op.drop_index('ix_disputes_id', table_name='disputes')
    op.drop_table('disputes')

    op.drop_index('ix_claim_adjudication_logs_claim_id', table_name='claim_adjudication_logs')
    op.drop_index('ix_claim_adjudication_logs_id', table_name='claim_adjudication_logs')
    op.drop_table('claim_adjudication_logs')

    op.drop_index('ix_chronic_registrations_scheme_id', table_name='chronic_registrations')
    op.drop_index('ix_chronic_registrations_member_id', table_name='chronic_registrations')
    op.drop_index('ix_chronic_registrations_id', table_name='chronic_registrations')
    op.drop_table('chronic_registrations')

    op.drop_index('ix_formulary_plan_option_id', table_name='formulary')
    op.drop_index('ix_formulary_id', table_name='formulary')
    op.drop_table('formulary')

    op.drop_index('ix_provider_networks_scheme_id', table_name='provider_networks')
    op.drop_index('ix_provider_networks_provider_id', table_name='provider_networks')
    op.drop_index('ix_provider_networks_id', table_name='provider_networks')
    op.drop_table('provider_networks')

    op.drop_index('ix_copayment_rules_scheme_id', table_name='copayment_rules')
    op.drop_index('ix_copayment_rules_id', table_name='copayment_rules')
    op.drop_table('copayment_rules')

    op.drop_index('ix_savings_accounts_member_id', table_name='savings_accounts')
    op.drop_index('ix_savings_accounts_id', table_name='savings_accounts')
    op.drop_table('savings_accounts')

    op.drop_index('ix_benefit_balances_scheme_id', table_name='benefit_balances')
    op.drop_index('ix_benefit_balances_member_id', table_name='benefit_balances')
    op.drop_index('ix_benefit_balances_id', table_name='benefit_balances')
    op.drop_table('benefit_balances')

    op.drop_index('ix_contribution_rates_plan_option_id', table_name='contribution_rates')
    op.drop_index('ix_contribution_rates_id', table_name='contribution_rates')
    op.drop_table('contribution_rates')

    op.drop_index('ix_nappi_codes_nappi_code', table_name='nappi_codes')
    op.drop_index('ix_nappi_codes_id', table_name='nappi_codes')
    op.drop_table('nappi_codes')

    # Remove added columns (reverse order per table)
    op.drop_column('providers', 'physical_address')

    op.drop_column('audit_logs', 'reason')
    op.drop_column('audit_logs', 'claim_rejection_code')
    op.drop_column('audit_logs', 'is_pmb_override')
    op.drop_column('audit_logs', 'ip_address')
    op.drop_column('audit_logs', 'user_role')
    op.drop_column('audit_logs', 'event_id')

    op.drop_column('claim_lines', 'is_pmb_override')
    op.drop_column('claim_lines', 'scheme_rate_cents')
    op.drop_column('claim_lines', 'copayment_cents')
    op.drop_column('claim_lines', 'benefit_bucket')
    op.drop_column('claim_lines', 'nappi_code_id')

    op.drop_column('dependants', 'effective_to')
    op.drop_column('dependants', 'effective_from')

    op.drop_column('members', 'popia_consent_date')
    op.drop_column('members', 'late_joiner_penalty')
    op.drop_column('members', 'waiting_period_end_date')
    op.drop_column('members', 'termination_reason')
    op.drop_column('members', 'physical_address')
    op.drop_column('members', 'passport_number')

    op.drop_column('tariff_codes', 'effective_year')
    op.drop_column('tariff_codes', 'requires_auth')
    op.drop_column('tariff_codes', 'discipline_codes')
    op.drop_column('tariff_codes', 'tariff_list')

    op.drop_column('icd10_codes', 'is_billable')
    op.drop_column('icd10_codes', 'gender_restriction')
    op.drop_column('icd10_codes', 'cdl_condition_name')
    op.drop_column('icd10_codes', 'is_cdl')

    op.drop_column('plan_options', 'tariff_multiplier')
    op.drop_column('plan_options', 'benefit_year')
    op.drop_column('plan_options', 'gp_referral_required')
    op.drop_column('plan_options', 'care_coordination_required')
    op.drop_column('plan_options', 'day_to_day_type')
    op.drop_column('plan_options', 'hospital_network')
