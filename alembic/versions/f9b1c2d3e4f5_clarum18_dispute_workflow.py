"""CLARUM-18 dispute workflow fields and history tables

Revision ID: f9b1c2d3e4f5
Revises: e4c69f835460
Create Date: 2026-07-25 12:40:00.000000
"""
from datetime import datetime, time, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9b1c2d3e4f5"
down_revision: Union[str, None] = "e4c69f835460"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("disputes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("transition_reason", sa.Text(), nullable=True))

    op.create_index("ix_disputes_status_changed_at", "disputes", ["status_changed_at"], unique=False)
    op.create_index("ix_disputes_sla_deadline", "disputes", ["sla_deadline"], unique=False)

    op.create_table(
        "dispute_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_dispute_comments_dispute_id", "dispute_comments", ["dispute_id"], unique=False)

    op.create_table(
        "dispute_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"]),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
    )
    op.create_index("ix_dispute_status_history_dispute_id", "dispute_status_history", ["dispute_id"], unique=False)

    bind = op.get_bind()
    disputes_table = sa.table(
        "disputes",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("admin_deadline", sa.Date),
        sa.column("status_changed_at", sa.DateTime(timezone=True)),
        sa.column("sla_deadline", sa.DateTime(timezone=True)),
    )
    history_table = sa.table(
        "dispute_status_history",
        sa.column("dispute_id", sa.Integer),
        sa.column("from_status", sa.String),
        sa.column("to_status", sa.String),
        sa.column("changed_by", sa.Integer),
        sa.column("changed_at", sa.DateTime(timezone=True)),
    )

    legacy_map = {
        "OPEN": "NEW",
        "UNDER_REVIEW": "INVESTIGATING",
        "UPHELD": "RESOLVED",
        "DISMISSED": "REJECTED",
        "ESCALATED_TO_CMS": "REJECTED",
    }

    rows = bind.execute(
        sa.select(
            disputes_table.c.id,
            disputes_table.c.status,
            disputes_table.c.created_at,
            disputes_table.c.updated_at,
            disputes_table.c.admin_deadline,
        )
    ).fetchall()

    for row in rows:
        created_at = row.created_at or datetime.now(timezone.utc)
        changed_at = row.updated_at or created_at
        mapped_status = legacy_map.get((row.status or "").upper(), (row.status or "NEW").upper())
        sla_deadline = None
        if row.admin_deadline is not None:
            sla_deadline = datetime.combine(row.admin_deadline, time.min, tzinfo=timezone.utc)
        bind.execute(
            disputes_table.update()
            .where(disputes_table.c.id == row.id)
            .values(
                status=mapped_status,
                status_changed_at=changed_at,
                sla_deadline=sla_deadline,
            )
        )
        bind.execute(
            history_table.insert().values(
                dispute_id=row.id,
                from_status=None,
                to_status=mapped_status,
                changed_by=None,
                changed_at=changed_at,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_dispute_status_history_dispute_id", table_name="dispute_status_history")
    op.drop_table("dispute_status_history")

    op.drop_index("ix_dispute_comments_dispute_id", table_name="dispute_comments")
    op.drop_table("dispute_comments")

    op.drop_index("ix_disputes_sla_deadline", table_name="disputes")
    op.drop_index("ix_disputes_status_changed_at", table_name="disputes")
    with op.batch_alter_table("disputes", schema=None) as batch_op:
        batch_op.drop_column("transition_reason")
        batch_op.drop_column("sla_deadline")
        batch_op.drop_column("status_changed_at")
