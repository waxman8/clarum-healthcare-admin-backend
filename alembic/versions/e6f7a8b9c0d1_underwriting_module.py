"""Add underwriting module: decisions, condition exclusions, member column migration.

Creates underwriting_decisions and member_condition_exclusions tables.
Migrates members.late_joiner_penalty (bool) to late_joiner_penalty_pct (int).
"""
from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "underwriting_decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scheme_id", sa.Integer, nullable=False, index=True),
        sa.Column("member_id", sa.Integer, nullable=False, index=True),
        sa.Column("decision_date", sa.Date, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # Prior cover
        sa.Column("has_prior_cover", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("prior_cover_years", sa.Numeric(5, 2), nullable=True),
        sa.Column("prior_cover_break_days", sa.Integer, nullable=True),
        sa.Column("prior_cover_proof_type", sa.String(50), nullable=True),
        sa.Column("prior_cover_schemes_json", sa.JSON, nullable=True),
        # Waiting period
        sa.Column("general_wp_months", sa.Integer, nullable=True),
        sa.Column("general_wp_end_date", sa.Date, nullable=True),
        # Late-joiner
        sa.Column("is_late_joiner", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("late_joiner_uncovered_years", sa.Integer, nullable=True),
        sa.Column("late_joiner_penalty_pct", sa.Integer, nullable=False, server_default="0"),
        # Contribution (frozen at decision time)
        sa.Column("base_monthly_contribution", sa.Integer, nullable=True),
        sa.Column("total_monthly_contribution", sa.Integer, nullable=True),
        # Audit
        sa.Column("created_by", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        # Phase 2 hook
        sa.Column("engine_version", sa.String(20), nullable=True),
        sa.Column("rules_triggered_json", sa.JSON, nullable=True),
    )

    op.create_table(
        "member_condition_exclusions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("underwriting_decision_id", sa.Integer, nullable=False, index=True),
        sa.Column("member_id", sa.Integer, nullable=False, index=True),
        sa.Column("scheme_id", sa.Integer, nullable=False),
        sa.Column("icd10_code", sa.String(20), nullable=False),
        sa.Column("condition_name", sa.String(200), nullable=True),
        sa.Column("is_pmb", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("exclusion_start_date", sa.Date, nullable=False),
        sa.Column("exclusion_end_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Migrate members.late_joiner_penalty (bool) → late_joiner_penalty_pct (int, default 0)
    op.add_column("members", sa.Column("late_joiner_penalty_pct", sa.Integer, nullable=False, server_default="0"))
    op.drop_column("members", "late_joiner_penalty")


def downgrade():
    op.add_column("members", sa.Column("late_joiner_penalty", sa.Boolean, nullable=False, server_default=sa.false()))
    op.drop_column("members", "late_joiner_penalty_pct")
    op.drop_table("member_condition_exclusions")
    op.drop_table("underwriting_decisions")
