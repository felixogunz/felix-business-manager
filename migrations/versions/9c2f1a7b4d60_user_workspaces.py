"""Add user workspace ownership and password reset fields."""

from alembic import op
import sqlalchemy as sa


revision = "9c2f1a7b4d60"
down_revision = "7f990fd042f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    def get_columns(table_name):
        return {
            column["name"]: column
            for column in sa.inspect(bind).get_columns(table_name)
        }

    # Add clients.user_id only if it does not already exist.
    client_columns = get_columns("clients")

    if "user_id" not in client_columns:
        op.add_column(
            "clients",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # Preserve existing ownership. Only assign user ID 1 to
    # clients that do not currently have an owner.
    null_owners = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM clients WHERE user_id IS NULL"
        )
    ).scalar_one()

    if null_owners:
        existing_user = bind.execute(
            sa.text("SELECT id FROM users WHERE id = 1")
        ).first()

        if existing_user is None:
            raise RuntimeError(
                "User ID 1 was not found. Cannot safely assign "
                "ownership to existing clients."
            )

        bind.execute(
            sa.text(
                "UPDATE clients SET user_id = 1 "
                "WHERE user_id IS NULL"
            )
        )

    # Ensure user_id is non-nullable.
    client_columns = get_columns("clients")

    if client_columns["user_id"]["nullable"]:
        op.alter_column(
            "clients",
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    # Add the foreign key only if it does not already exist.
    foreign_keys = sa.inspect(bind).get_foreign_keys("clients")

    has_user_foreign_key = any(
        fk.get("constrained_columns") == ["user_id"]
        and fk.get("referred_table") == "users"
        for fk in foreign_keys
    )

    if not has_user_foreign_key:
        op.create_foreign_key(
            "fk_clients_user_id_users",
            "clients",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Add the index only if one does not already exist.
    indexes = sa.inspect(bind).get_indexes("clients")

    has_user_index = any(
        index.get("column_names") == ["user_id"]
        for index in indexes
    )

    if not has_user_index:
        op.create_index(
            "ix_clients_user_id",
            "clients",
            ["user_id"],
        )

    # Add password-reset fields only if missing.
    user_columns = get_columns("users")

    if "password_reset_token_hash" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "password_reset_token_hash",
                sa.String(255),
                nullable=True,
            ),
        )

    user_columns = get_columns("users")

    if "password_reset_expires_at" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "password_reset_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    raise RuntimeError(
        "This migration must not be automatically downgraded."
    )
