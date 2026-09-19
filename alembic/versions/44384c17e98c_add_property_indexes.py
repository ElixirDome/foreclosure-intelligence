"""add property indexes

Revision ID: 44384c17e98c
Revises: 
Create Date: 2026-08-21 06:46:28.976817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44384c17e98c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
  
    op.create_index(op.f('ix_properties_bedrooms'), 'properties', ['bedrooms'], unique=False)
    op.create_index(op.f('ix_properties_price'), 'properties', ['price'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    
    op.drop_index(op.f('ix_properties_price'), table_name='properties')
    op.drop_index(op.f('ix_properties_bedrooms'), table_name='properties')
   
