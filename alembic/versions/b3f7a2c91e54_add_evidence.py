"""add evidence

Revision ID: b3f7a2c91e54
Revises: 249c18e4a582
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3f7a2c91e54"
down_revision: Union[str, Sequence[str], None] = "249c18e4a582"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("source_text", sa.String(), nullable=True),
        sa.Column("extraction_method", sa.String(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_evidence_property_id",
        "evidence",
        ["property_id"],
        unique=False,
    )

    op.create_index(
        "ix_evidence_document_id",
        "evidence",
        ["document_id"],
        unique=False,
    )

    op.create_index(
        "ix_evidence_field",
        "evidence",
        ["field"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evidence_field",
        table_name="evidence",
    )

    op.drop_index(
        "ix_evidence_document_id",
        table_name="evidence",
    )

    op.drop_index(
        "ix_evidence_property_id",
        table_name="evidence",
    )

    op.drop_table("evidence")