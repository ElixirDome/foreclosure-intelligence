"""add property indexes

Revision ID: 44384c17e98c
Revises: 
Create Date: 2026-08-21 06:46:28.976817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44384c17e98c'
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"

def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "properties",
        "id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )
    op.alter_column(
        "properties",
        "address",
        existing_type=sa.Text(),
        type_=sa.String(),
        existing_nullable=False,
    )
  
    op.create_index(op.f('ix_properties_bedrooms'), 'properties', ['bedrooms'], unique=False)
    op.create_index(op.f('ix_properties_price'), 'properties', ['price'], unique=False)




def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f("ix_properties_price"), table_name="properties")
    op.drop_index(op.f("ix_properties_bedrooms"), table_name="properties")

    op.alter_column(
        "properties",
        "address",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "properties",
        "id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        autoincrement=True,
    )
