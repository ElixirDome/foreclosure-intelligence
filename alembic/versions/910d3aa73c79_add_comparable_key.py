from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "910d3aa73c79"
down_revision: Union[str, Sequence[str], None] = "75d2bf462605"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_comparables",
        sa.Column(
            "comparable_key",
            sa.String(),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE market_comparables
            SET comparable_key =
                LOWER(TRIM(source))
                || '|'
                || LOWER(TRIM(address))
                || '|'
                || area_sqft::text
                || '|'
                || sale_price::text
                || '|'
                || COALESCE(sale_date::text, '')
            WHERE comparable_key IS NULL
            """
        )
    )

    op.alter_column(
        "market_comparables",
        "comparable_key",
        nullable=False,
    )

    op.create_index(
        "ix_market_comparables_comparable_key",
        "market_comparables",
        ["comparable_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_comparables_comparable_key",
        table_name="market_comparables",
    )

    op.drop_column(
        "market_comparables",
        "comparable_key",
    )