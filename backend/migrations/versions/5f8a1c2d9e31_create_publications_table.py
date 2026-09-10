"""create publications table

Revision ID: 5f8a1c2d9e31
Revises: 6eb26de38e4e
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f8a1c2d9e31"
down_revision: Union[str, Sequence[str], None] = "6eb26de38e4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the durable publications table."""

    op.create_table(
        "publications",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "social_account_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "publication_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "external_post_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "retry_after_seconds",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "first_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "publication_metadata",
            sa.JSON(),
            nullable=True,
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
            ["post_id"],
            ["posts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_key",
            name="uq_publications_publication_key",
        ),
        sa.UniqueConstraint(
            "post_id",
            "social_account_id",
            name="uq_publications_post_social_account",
        ),
    )

    op.create_index(
        "ix_publications_post_id",
        "publications",
        ["post_id"],
        unique=False,
    )

    op.create_index(
        "ix_publications_social_account_id",
        "publications",
        ["social_account_id"],
        unique=False,
    )

    op.create_index(
        "ix_publications_platform",
        "publications",
        ["platform"],
        unique=False,
    )

    op.create_index(
        "ix_publications_publication_key",
        "publications",
        ["publication_key"],
        unique=True,
    )

    op.create_index(
        "ix_publications_external_post_id",
        "publications",
        ["external_post_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the durable publications table."""

    op.drop_index(
        "ix_publications_external_post_id",
        table_name="publications",
    )

    op.drop_index(
        "ix_publications_publication_key",
        table_name="publications",
    )

    op.drop_index(
        "ix_publications_platform",
        table_name="publications",
    )

    op.drop_index(
        "ix_publications_social_account_id",
        table_name="publications",
    )

    op.drop_index(
        "ix_publications_post_id",
        table_name="publications",
    )

    op.drop_table("publications")