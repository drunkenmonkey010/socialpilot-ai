"""add publication idempotency fields

Revision ID: 6eb26de38e4e
Revises: 9f31b34c1261
Create Date: 2026-09-08 18:01:36.670874

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6eb26de38e4e"
down_revision: Union[str, Sequence[str], None] = "9f31b34c1261"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add durable publication idempotency fields to posts."""

    op.add_column(
        "posts",
        sa.Column(
            "publication_key",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "posts",
        sa.Column(
            "external_post_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "posts",
        sa.Column(
            "publication_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_posts_publication_key",
        "posts",
        ["publication_key"],
        unique=True,
    )

    op.create_index(
        "ix_posts_external_post_id",
        "posts",
        ["external_post_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove durable publication idempotency fields from posts."""

    op.drop_index(
        "ix_posts_external_post_id",
        table_name="posts",
    )

    op.drop_index(
        "ix_posts_publication_key",
        table_name="posts",
    )

    op.drop_column(
        "posts",
        "publication_attempts",
    )

    op.drop_column(
        "posts",
        "external_post_id",
    )

    op.drop_column(
        "posts",
        "publication_key",
    )