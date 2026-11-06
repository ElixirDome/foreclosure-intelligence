"""Merge migration branches

Revision ID: dd9a2f8bca9b
Revises: 99f0e1d2c3b4, c7d8e9f0a1b2
Create Date: 2026-11-04 07:18:37.432567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd9a2f8bca9b'
down_revision: Union[str, Sequence[str], None] = ('99f0e1d2c3b4', 'c7d8e9f0a1b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
