"""add document chunks and enrich documents

Revision ID: c4e8d1a0b2f3
Revises: b3f7a2c91e54
Create Date: 2026-10-08

Phase 1 — Document architecture:
- Enrich documents with filename, mime_type, storage_path, extracted_text
- Create document_chunks as the retrieval unit
- Allow evidence to optionally point at a specific chunk
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8d1a0b2f3"
down_revision: Union[str, Sequence[str], None] = "b3f7a2c91e54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "documents" in tables:
        doc_cols = {c["name"] for c in insp.get_columns("documents")}
        for col_name, col_type in (
            ("filename", sa.String()),
            ("mime_type", sa.String()),
            ("storage_path", sa.String()),
            ("extracted_text", sa.Text()),
        ):
            if col_name not in doc_cols:
                op.add_column("documents", sa.Column(col_name, col_type, nullable=True))

    if "document_chunks" not in tables:
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["documents.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    insp = sa.inspect(bind)
    if "document_chunks" in insp.get_table_names():
        chunk_indexes = {ix["name"] for ix in insp.get_indexes("document_chunks")}
        if op.f("ix_document_chunks_document_id") not in chunk_indexes:
            op.create_index(
                op.f("ix_document_chunks_document_id"),
                "document_chunks",
                ["document_id"],
                unique=False,
            )
        if op.f("ix_document_chunks_page_number") not in chunk_indexes:
            op.create_index(
                op.f("ix_document_chunks_page_number"),
                "document_chunks",
                ["page_number"],
                unique=False,
            )
        if "ix_document_chunks_document_id_chunk_index" not in chunk_indexes:
            op.create_index(
                "ix_document_chunks_document_id_chunk_index",
                "document_chunks",
                ["document_id", "chunk_index"],
                unique=True,
            )

    if "evidence" in tables:
        ev_cols = {c["name"] for c in insp.get_columns("evidence")}
        if "document_chunk_id" not in ev_cols:
            op.add_column(
                "evidence",
                sa.Column("document_chunk_id", sa.Integer(), nullable=True),
            )
        ev_indexes = {ix["name"] for ix in insp.get_indexes("evidence")}
        if op.f("ix_evidence_document_chunk_id") not in ev_indexes:
            op.create_index(
                op.f("ix_evidence_document_chunk_id"),
                "evidence",
                ["document_chunk_id"],
                unique=False,
            )
        ev_fks = insp.get_foreign_keys("evidence")
        has_fk = any(
            fk.get("referred_table") == "document_chunks" and fk.get("constrained_columns") == ["document_chunk_id"]
            for fk in ev_fks
        )
        if not has_fk and bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_evidence_document_chunk_id",
                "evidence",
                "document_chunks",
                ["document_chunk_id"],
                ["id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "evidence" in tables:
        ev_fks = {fk.get("name") for fk in insp.get_foreign_keys("evidence") if fk.get("name")}
        if "fk_evidence_document_chunk_id" in ev_fks:
            op.drop_constraint(
                "fk_evidence_document_chunk_id",
                "evidence",
                type_="foreignkey",
            )
        ev_indexes = {ix["name"] for ix in insp.get_indexes("evidence")}
        if op.f("ix_evidence_document_chunk_id") in ev_indexes:
            op.drop_index(
                op.f("ix_evidence_document_chunk_id"),
                table_name="evidence",
            )
        ev_cols = {c["name"] for c in insp.get_columns("evidence")}
        if "document_chunk_id" in ev_cols:
            op.drop_column("evidence", "document_chunk_id")

    if "document_chunks" in tables:
        chunk_indexes = {ix["name"] for ix in insp.get_indexes("document_chunks")}
        for ix_name in (
            "ix_document_chunks_document_id_chunk_index",
            op.f("ix_document_chunks_page_number"),
            op.f("ix_document_chunks_document_id"),
        ):
            if ix_name in chunk_indexes:
                op.drop_index(ix_name, table_name="document_chunks")
        op.drop_table("document_chunks")

    if "documents" in tables:
        doc_cols = {c["name"] for c in insp.get_columns("documents")}
        for col_name in ("extracted_text", "storage_path", "mime_type", "filename"):
            if col_name in doc_cols:
                op.drop_column("documents", col_name)
