from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f31b34c1261"
down_revision: Union[str, Sequence[str], None] = "258587792be4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_accounts",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "account_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "access_token",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "refresh_token",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_social_accounts_user_id",
        "social_accounts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_social_accounts_user_id",
        table_name="social_accounts",
    )

    op.drop_table("social_accounts")