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
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "properties" in tables:
        prop_cols = {c["name"] for c in insp.get_columns("properties")}
        if "emd" not in prop_cols:
            op.add_column("properties", sa.Column("emd", sa.Numeric(), nullable=True))
        if "reserve_price" not in prop_cols:
            op.add_column("properties", sa.Column("reserve_price", sa.Numeric(), nullable=True))

        prop_indexes = {ix["name"] for ix in insp.get_indexes("properties")}
        for ix_name, col in (
            ("ix_properties_auction_date", "auction_date"),
            ("ix_properties_foreclosure_status", "foreclosure_status"),
            ("ix_properties_property_type", "property_type"),
        ):
            if ix_name not in prop_indexes:
                op.create_index(ix_name, "properties", [col])

    if "property_documents" in tables:
        pd_indexes = {ix["name"] for ix in insp.get_indexes("property_documents")}
        if "ix_property_documents_property_id" not in pd_indexes:
            op.create_index("ix_property_documents_property_id", "property_documents", ["property_id"])
        if "ix_property_documents_document_id" not in pd_indexes:
            op.create_index("ix_property_documents_document_id", "property_documents", ["document_id"])

        # Deduplicate using ANSI SQL compatible with both SQLite and Postgres
        op.execute(
            """
            DELETE FROM property_documents
            WHERE id NOT IN (
                SELECT MIN(id) FROM property_documents GROUP BY property_id, document_id
            )
            """
        )
        unique_cons = {u["name"] for u in insp.get_unique_constraints("property_documents")}
        if "uq_property_document" not in unique_cons and bind.dialect.name != "sqlite":
            op.create_unique_constraint(
                "uq_property_document",
                "property_documents",
                ["property_id", "document_id"],
            )

    if "connected_sources" not in tables:
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
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "connected_sources" in tables:
        op.drop_table("connected_sources")

    if "property_documents" in tables:
        unique_cons = {u["name"] for u in insp.get_unique_constraints("property_documents")}
        if "uq_property_document" in unique_cons:
            op.drop_constraint("uq_property_document", "property_documents", type_="unique")
        pd_indexes = {ix["name"] for ix in insp.get_indexes("property_documents")}
        if "ix_property_documents_document_id" in pd_indexes:
            op.drop_index("ix_property_documents_document_id", table_name="property_documents")
        if "ix_property_documents_property_id" in pd_indexes:
            op.drop_index("ix_property_documents_property_id", table_name="property_documents")

    if "properties" in tables:
        prop_indexes = {ix["name"] for ix in insp.get_indexes("properties")}
        for ix_name in (
            "ix_properties_property_type",
            "ix_properties_foreclosure_status",
            "ix_properties_auction_date",
        ):
            if ix_name in prop_indexes:
                op.drop_index(ix_name, table_name="properties")
        prop_cols = {c["name"] for c in insp.get_columns("properties")}
        if "reserve_price" in prop_cols:
            op.drop_column("properties", "reserve_price")
        if "emd" in prop_cols:
            op.drop_column("properties", "emd")
