from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "910d3aa73c79"
down_revision: Union[str, Sequence[str], None] = "75d2bf462605"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    insp = sa.inspect(connection)
    cols = {c["name"] for c in insp.get_columns("market_comparables")}

    if "comparable_key" not in cols:
        op.add_column(
            "market_comparables",
            sa.Column(
                "comparable_key",
                sa.String(),
                nullable=True,
            ),
        )

    connection.execute(
        sa.text(
            """
            UPDATE market_comparables
            SET comparable_key =
                LOWER(TRIM(source))
                || '|'
                || LOWER(TRIM(address))
                || '|'
                || CAST(area_sqft AS TEXT)
                || '|'
                || CAST(sale_price AS TEXT)
                || '|'
                || COALESCE(CAST(sale_date AS TEXT), '')
            WHERE comparable_key IS NULL
            """
        )
    )

    if connection.dialect.name != "sqlite":
        op.alter_column(
            "market_comparables",
            "comparable_key",
            nullable=False,
        )

    indexes = {ix["name"] for ix in insp.get_indexes("market_comparables")}
    if "ix_market_comparables_comparable_key" not in indexes:
        op.create_index(
            "ix_market_comparables_comparable_key",
            "market_comparables",
            ["comparable_key"],
            unique=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    insp = sa.inspect(connection)
    indexes = {ix["name"] for ix in insp.get_indexes("market_comparables")}
    if "ix_market_comparables_comparable_key" in indexes:
        op.drop_index(
            "ix_market_comparables_comparable_key",
            table_name="market_comparables",
        )

    cols = {c["name"] for c in insp.get_columns("market_comparables")}
    if "comparable_key" in cols:
        op.drop_column(
            "market_comparables",
            "comparable_key",
        )
