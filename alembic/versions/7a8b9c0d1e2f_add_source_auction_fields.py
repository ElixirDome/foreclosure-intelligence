"""add source auction fields

Revision ID: 7a8b9c0d1e2f
Revises: 99f0e1d2c3b4
Create Date: 2026-10-28 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '99f0e1d2c3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    cols = {c['name'] for c in inspector.get_columns('properties')}

    new_columns = [
        ('increment_amount', sa.Numeric()),
        ('auction_start', sa.DateTime()),
        ('auction_end', sa.DateTime()),
        ('possession_type', sa.String()),
        ('property_sub_type', sa.String()),
        ('district', sa.String()),
        ('state', sa.String()),
        ('pincode', sa.String()),
        ('bank_name', sa.String()),
        ('branch_name', sa.String()),
        ('raw_status', sa.String()),
        ('extra_data', sa.JSON()),
    ]

    for col_name, col_type in new_columns:
        if col_name not in cols:
            op.add_column('properties', sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    columns_to_drop = [
        'extra_data',
        'raw_status',
        'branch_name',
        'bank_name',
        'pincode',
        'state',
        'district',
        'property_sub_type',
        'possession_type',
        'auction_end',
        'auction_start',
        'increment_amount',
    ]
    for col in columns_to_drop:
        op.drop_column('properties', col)
