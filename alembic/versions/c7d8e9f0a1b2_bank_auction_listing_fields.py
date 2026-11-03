"""Store source auction identifiers, listing photos and inspection deadlines.

Revision ID: c7d8e9f0a1b2
Revises: f1a2b3c4d5e6
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in inspect(bind).get_columns("properties")}
    columns = (
        ("property_unique_id", sa.String()),
        ("auction_id", sa.String()),
        ("property_images", sa.JSON()),
        ("inspection_start", sa.DateTime()),
        ("inspection_end", sa.DateTime()),
        ("emd_deadline", sa.DateTime()),
        ("listing_url", sa.String()),
    )
    for name, column_type in columns:
        if name not in existing:
            op.add_column("properties", sa.Column(name, column_type, nullable=True))
    indexes = {index["name"] for index in inspect(bind).get_indexes("properties")}
    for name, column in (("ix_properties_property_unique_id", "property_unique_id"), ("ix_properties_auction_id", "auction_id")):
        if name not in indexes:
            op.create_index(name, "properties", [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in inspect(bind).get_indexes("properties")}
    for name in ("ix_properties_auction_id", "ix_properties_property_unique_id"):
        if name in indexes:
            op.drop_index(name, table_name="properties")
    columns = {column["name"] for column in inspect(bind).get_columns("properties")}
    for name in ("listing_url", "emd_deadline", "inspection_end", "inspection_start", "property_images", "auction_id", "property_unique_id"):
        if name in columns:
            op.drop_column("properties", name)
