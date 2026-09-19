"""add survey number to properties

Revision ID: e1cbaff27444
Revises: b4f1218e7862
Create Date: 2026-09-17 18:31:10.263349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1cbaff27444'
down_revision: Union[str, Sequence[str], None] = 'b4f1218e7862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("survey_number", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(
        "properties",
        "survey_number",
    )
