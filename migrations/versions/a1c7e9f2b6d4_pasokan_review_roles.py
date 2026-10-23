"""Pasokan review workflow and admin/supplier roles.

Revision ID: a1c7e9f2b6d4
Revises: 696f721989bd
Create Date: 2026-10-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1c7e9f2b6d4"
down_revision = "696f721989bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert roles to admin/supplier and add the pasokan review fields."""
    # Widen the enums first so existing donor/receiver rows stay valid while
    # they are converted to the new supplier role.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum("admin", "donor", "receiver", name="user_role_enum"),
            type_=sa.Enum(
                "admin", "supplier", "donor", "receiver", name="user_role_enum"
            ),
            existing_nullable=False,
        )

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=sa.Enum("donor", "receiver", name="org_type_enum"),
            type_=sa.Enum("supplier", "donor", "receiver", name="org_type_enum"),
            existing_nullable=False,
        )

    op.execute("UPDATE users SET role = 'supplier' WHERE role IN ('donor', 'receiver')")
    op.execute("UPDATE organizations SET type = 'supplier'")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum(
                "admin", "supplier", "donor", "receiver", name="user_role_enum"
            ),
            type_=sa.Enum("admin", "supplier", name="user_role_enum"),
            existing_nullable=False,
        )

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=sa.Enum("supplier", "donor", "receiver", name="org_type_enum"),
            type_=sa.Enum("supplier", name="org_type_enum"),
            existing_nullable=False,
        )

    with op.batch_alter_table("surplus_listings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "review_status",
                sa.Enum(
                    "pending",
                    "approved",
                    "rejected",
                    name="pasokan_review_status_enum",
                ),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("reviewed_by", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("review_note", sa.Text(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_surplus_listings_reviewed_by_users",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_surplus_listings_review_status_created_at",
            ["review_status", "created_at"],
            unique=False,
        )

    # Listings created before this revision were already published, so keep
    # them visible instead of sending every historical row back to review.
    op.execute("UPDATE surplus_listings SET review_status = 'approved'")

    op.drop_table("claims")


def downgrade() -> None:
    """Restore the claim table and the legacy donor/receiver roles."""
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("receiver_org_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "picked_up",
                "cancelled",
                name="claim_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(), nullable=False),
        sa.Column("picked_up_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["surplus_listings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["receiver_org_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("claims", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_claims_listing_id"), ["listing_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_claims_receiver_org_id"),
            ["receiver_org_id"],
            unique=False,
        )

    with op.batch_alter_table("surplus_listings", schema=None) as batch_op:
        batch_op.drop_index("ix_surplus_listings_review_status_created_at")
        batch_op.drop_constraint(
            "fk_surplus_listings_reviewed_by_users", type_="foreignkey"
        )
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("review_status")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum("admin", "supplier", name="user_role_enum"),
            type_=sa.Enum(
                "admin", "supplier", "donor", "receiver", name="user_role_enum"
            ),
            existing_nullable=False,
        )

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=sa.Enum("supplier", name="org_type_enum"),
            type_=sa.Enum("supplier", "donor", "receiver", name="org_type_enum"),
            existing_nullable=False,
        )

    op.execute("UPDATE users SET role = 'donor' WHERE role = 'supplier'")
    op.execute("UPDATE organizations SET type = 'donor'")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum(
                "admin", "supplier", "donor", "receiver", name="user_role_enum"
            ),
            type_=sa.Enum("admin", "donor", "receiver", name="user_role_enum"),
            existing_nullable=False,
        )

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=sa.Enum("supplier", "donor", "receiver", name="org_type_enum"),
            type_=sa.Enum("donor", "receiver", name="org_type_enum"),
            existing_nullable=False,
        )
