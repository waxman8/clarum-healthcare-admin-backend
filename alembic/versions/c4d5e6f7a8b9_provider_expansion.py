"""Provider model expansion — full industry fields + discipline_codes table.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    # ---- discipline_codes reference table ----
    op.create_table(
        "discipline_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    # ---- providers: new columns ----
    with op.batch_alter_table("providers") as batch_op:
        # Identity
        batch_op.add_column(sa.Column("registered_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("hpcsa_number", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("sapc_number", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("dispensing_license", sa.Boolean, nullable=False, server_default=sa.false()))
        # Discipline
        batch_op.add_column(sa.Column("provider_category", sa.String(50), nullable=True))
        # Contact
        batch_op.add_column(sa.Column("telephone", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("fax", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("website", sa.String(255), nullable=True))
        # Address
        batch_op.add_column(sa.Column("address_line1", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("suburb", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("province", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("postal_code", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("latitude", sa.Numeric(10, 6), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Numeric(10, 6), nullable=True))
        # Banking
        batch_op.add_column(sa.Column("bank_name", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("branch_code", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("account_number", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("account_type", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("account_holder", sa.String(255), nullable=True))
        # Status/Flags
        batch_op.add_column(sa.Column("contracted", sa.Boolean, nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_blacklisted", sa.Boolean, nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("blacklist_reason", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("blacklist_date", sa.Date, nullable=True))
        # Hospital-specific
        batch_op.add_column(sa.Column("hospital_level", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("bed_count", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("icu_bed_count", sa.Integer, nullable=True))
        # provider_type now nullable (superseded by provider_category)
        batch_op.alter_column("provider_type", existing_type=sa.String(50), nullable=True)


def downgrade():
    with op.batch_alter_table("providers") as batch_op:
        for col in [
            "registered_name", "hpcsa_number", "sapc_number", "dispensing_license",
            "provider_category", "telephone", "fax", "website",
            "address_line1", "suburb", "city", "province", "postal_code",
            "latitude", "longitude",
            "bank_name", "branch_code", "account_number", "account_type", "account_holder",
            "contracted", "is_blacklisted", "blacklist_reason", "blacklist_date",
            "hospital_level", "bed_count", "icu_bed_count",
        ]:
            batch_op.drop_column(col)
        batch_op.alter_column("provider_type", existing_type=sa.String(50), nullable=False)

    op.drop_table("discipline_codes")
