"""restore document chunk composite index

Revision ID: 66c1710f4924
Revises: 881ea67e2433
Create Date: 2026-10-21 06:29:50.161563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66c1710f4924'
down_revision: Union[str, Sequence[str], None] = '881ea67e2433'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "document_chunks" in insp.get_table_names():
        indexes = {ix["name"] for ix in insp.get_indexes("document_chunks")}
        if "ix_document_chunks_document_id_chunk_index" not in indexes:
            op.create_index(
                "ix_document_chunks_document_id_chunk_index",
                "document_chunks",
                ["document_id", "chunk_index"],
                unique=True,
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "document_chunks" in insp.get_table_names():
        indexes = {ix["name"] for ix in insp.get_indexes("document_chunks")}
        if "ix_document_chunks_document_id_chunk_index" in indexes:
            op.drop_index("ix_document_chunks_document_id_chunk_index", table_name="document_chunks")
