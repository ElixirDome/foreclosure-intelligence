"""add property key

Revision ID: b4f1218e7862
Revises: 68faa821de7d
Create Date: 2026-09-11 19:39:27.618119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f1218e7862'
down_revision: Union[str, Sequence[str], None] = '68faa821de7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("property_key", sa.String(), nullable=True),
    )

    op.create_index(
        "ix_properties_property_key",
        "properties",
        ["property_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_properties_property_key",
        table_name="properties",
    )

    op.drop_column(
        "properties",
        "property_key",
    )
