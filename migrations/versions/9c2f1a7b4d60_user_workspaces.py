"""Add user workspace ownership and password reset fields."""

from alembic import op
import sqlalchemy as sa


revision = "9c2f1a7b4d60"
down_revision = "7f990fd042f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Never silently assign existing data to a missing account.
    existing_user = bind.execute(
        sa.text("SELECT id FROM users WHERE id = 1")
    ).first()

    if existing_user is None:
        raise RuntimeError(
            "User ID 1 was not found. Stop and verify the existing users "
            "before migrating client ownership."
        )

    op.add_column(
        "clients",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    # Preserve the existing clients by assigning them to the existing owner.
    op.execute(sa.text("UPDATE clients SET user_id = 1"))

    op.alter_column(
        "clients",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "fk_clients_user_id_users",
        "clients",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_clients_user_id",
        "clients",
        ["user_id"],
    )

    op.add_column(
        "users",
        sa.Column("password_reset_token_hash", sa.String(255), nullable=True),
    )

    op.add_column(
        "users",
        sa.Column(
            "password_reset_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # This migration changes ownership and adds account-security fields.
    # Do not automatically reverse it because doing so removes ownership data.
    raise RuntimeError(
        "This migration must not be automatically downgraded."
    )