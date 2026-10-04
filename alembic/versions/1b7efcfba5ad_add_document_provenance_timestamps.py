"""add document provenance timestamps

Revision ID: 1b7efcfba5ad
Revises: a20afb86dd17
Create Date: 2026-09-29 07:33:11.062451

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1b7efcfba5ad'
down_revision: Union[str, Sequence[str], None] = 'a20afb86dd17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add new columns temporarily as nullable because existing rows need values.
    op.add_column(
        "documents",
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )

    # Preserve existing document history.
    op.execute(
        """
        UPDATE documents
        SET
            first_seen_at = fetched_at,
            last_seen_at = fetched_at
        WHERE first_seen_at IS NULL
           OR last_seen_at IS NULL
        """
    )

    # Now that every existing row has values, enforce NOT NULL.
    op.alter_column(
        "documents",
        "first_seen_at",
        nullable=False,
    )

    op.alter_column(
        "documents",
        "last_seen_at",
        nullable=False,
    )

    # fetched_at has now been migrated into the new fields.
    op.drop_column("documents", "fetched_at")


def downgrade() -> None:
    """Downgrade schema."""

    op.add_column(
        "documents",
        sa.Column(
            "fetched_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    # Restore the old timestamp using first_seen_at.
    op.execute(
        """
        UPDATE documents
        SET fetched_at = first_seen_at
        WHERE fetched_at IS NULL
        """
    )

    op.alter_column(
        "documents",
        "fetched_at",
        nullable=False,
    )

    op.drop_column("documents", "last_seen_at")
    op.drop_column("documents", "first_seen_at")