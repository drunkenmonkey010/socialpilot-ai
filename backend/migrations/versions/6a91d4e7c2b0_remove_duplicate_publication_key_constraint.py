"""remove duplicate publication key constraint

Revision ID: 6a91d4e7c2b0
Revises: 5f8a1c2d9e31
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6a91d4e7c2b0"
down_revision: Union[str, Sequence[str], None] = "5f8a1c2d9e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove the redundant publication key unique constraint."""

    op.drop_constraint(
        "uq_publications_publication_key",
        "publications",
        type_="unique",
    )


def downgrade() -> None:
    """Restore the publication key unique constraint."""

    op.create_unique_constraint(
        "uq_publications_publication_key",
        "publications",
        ["publication_key"],
    )