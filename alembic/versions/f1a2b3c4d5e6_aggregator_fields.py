"""connected sources, reserve/emd, document link uniqueness, indexes

Revision ID: f1a2b3c4d5e6
Revises: c4e8d1a0b2f3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c4e8d1a0b2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("emd", sa.Numeric(), nullable=True))
    op.add_column("properties", sa.Column("reserve_price", sa.Numeric(), nullable=True))
    op.create_index("ix_properties_auction_date", "properties", ["auction_date"])
    op.create_index("ix_properties_foreclosure_status", "properties", ["foreclosure_status"])
    op.create_index("ix_properties_property_type", "properties", ["property_type"])
    op.create_index("ix_property_documents_property_id", "property_documents", ["property_id"])
    op.create_index("ix_property_documents_document_id", "property_documents", ["document_id"])
    op.execute(
        """
        DELETE FROM property_documents a
        USING property_documents b
        WHERE a.id > b.id
          AND a.property_id = b.property_id
          AND a.document_id = b.document_id
        """
    )
    op.create_unique_constraint(
        "uq_property_document",
        "property_documents",
        ["property_id", "document_id"],
    )
    op.create_table(
        "connected_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False, unique=True),
        sa.Column("adapter_key", sa.String(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("connected_sources")
    op.drop_constraint("uq_property_document", "property_documents", type_="unique")
    op.drop_index("ix_property_documents_document_id", table_name="property_documents")
    op.drop_index("ix_property_documents_property_id", table_name="property_documents")
    op.drop_index("ix_properties_property_type", table_name="properties")
    op.drop_index("ix_properties_foreclosure_status", table_name="properties")
    op.drop_index("ix_properties_auction_date", table_name="properties")
    op.drop_column("properties", "reserve_price")
    op.drop_column("properties", "emd")
