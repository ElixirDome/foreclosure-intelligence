"""add document_chunk_id foreign key to evidence

Revision ID: ee3edbd81818
Revises: c4e8d1a0b2f3
Create Date: 2026-10-17 19:33:41.001755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee3edbd81818'
down_revision: Union[str, Sequence[str], None] = 'c4e8d1a0b2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "evidence" in insp.get_table_names():
        ev_fks = insp.get_foreign_keys("evidence")
        has_fk = any(
            fk.get("referred_table") == "document_chunks" and fk.get("constrained_columns") == ["document_chunk_id"]
            for fk in ev_fks
        )
        if not has_fk and bind.dialect.name != "sqlite":
            op.create_foreign_key(None, 'evidence', 'document_chunks', ['document_chunk_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "evidence" in insp.get_table_names():
        ev_fks = insp.get_foreign_keys("evidence")
        fk_names = {fk.get("name") for fk in ev_fks if fk.get("name")}
        for name in ("fk_evidence_document_chunk_id", "evidence_document_chunk_id_fkey"):
            if name in fk_names:
                op.drop_constraint(
                    name,
                    "evidence",
                    type_="foreignkey",
                )
