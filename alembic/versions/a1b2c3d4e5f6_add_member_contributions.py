"""add member_contributions table

Revision ID: a1b2c3d4e5f6
Revises: 03ec8fb25fcd
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '03ec8fb25fcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'member_contributions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False, index=True),
        sa.Column('scheme_id', sa.Integer(), sa.ForeignKey('schemes.id'), nullable=False, index=True),
        sa.Column('billing_month', sa.Date(), nullable=False),
        sa.Column('principal_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('adult_dependant_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('adult_dependant_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('child_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('child_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('child_cap_applied', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('late_joiner_penalty_pct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('late_joiner_surcharge_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount_due_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount_paid_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='generated'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('member_id', 'billing_month', name='uq_member_contribution'),
    )


def downgrade() -> None:
    op.drop_table('member_contributions')
