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
    op.add_column(
        "documents",
        sa.Column("filename", sa.String(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("mime_type", sa.String(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("storage_path", sa.String(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )

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
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_page_number"),
        "document_chunks",
        ["page_number"],
        unique=False,
    )
    # Useful for ordered retrieval of a document's chunks.
    op.create_index(
        "ix_document_chunks_document_id_chunk_index",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=True,
    )

    op.add_column(
        "evidence",
        sa.Column("document_chunk_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_evidence_document_chunk_id"),
        "evidence",
        ["document_chunk_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_evidence_document_chunk_id",
        "evidence",
        "document_chunks",
        ["document_chunk_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evidence_document_chunk_id",
        "evidence",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_evidence_document_chunk_id"),
        table_name="evidence",
    )
    op.drop_column("evidence", "document_chunk_id")

    op.drop_index(
        "ix_document_chunks_document_id_chunk_index",
        table_name="document_chunks",
    )
    op.drop_index(
        op.f("ix_document_chunks_page_number"),
        table_name="document_chunks",
    )
    op.drop_index(
        op.f("ix_document_chunks_document_id"),
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")

    op.drop_column("documents", "extracted_text")
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "filename")
