"""merge evidence chunk foreign key and aggregator fields

Revision ID: 881ea67e2433
Revises: ee3edbd81818, f1a2b3c4d5e6
Create Date: 2026-10-20 16:18:00.628135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '881ea67e2433'
down_revision: Union[str, Sequence[str], None] = ('ee3edbd81818', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
