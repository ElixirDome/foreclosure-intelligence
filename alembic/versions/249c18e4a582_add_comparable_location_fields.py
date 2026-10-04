"""add comparable location fields

Revision ID: 249c18e4a582
Revises: 910d3aa73c79
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "249c18e4a582"
down_revision: Union[str, Sequence[str], None] = "910d3aa73c79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_comparables",
        sa.Column("city", sa.String(), nullable=True),
    )

    op.add_column(
        "market_comparables",
        sa.Column("locality", sa.String(), nullable=True),
    )

    op.create_index(
        "ix_market_comparables_city",
        "market_comparables",
        ["city"],
        unique=False,
    )

    op.create_index(
        "ix_market_comparables_locality",
        "market_comparables",
        ["locality"],
        unique=False,
    )

    op.create_index(
        "ix_market_comparables_property_type",
        "market_comparables",
        ["property_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_comparables_property_type",
        table_name="market_comparables",
    )

    op.drop_index(
        "ix_market_comparables_locality",
        table_name="market_comparables",
    )

    op.drop_index(
        "ix_market_comparables_city",
        table_name="market_comparables",
    )

    op.drop_column("market_comparables", "locality")
    op.drop_column("market_comparables", "city")