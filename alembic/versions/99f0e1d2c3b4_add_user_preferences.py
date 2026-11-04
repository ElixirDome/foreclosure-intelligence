"""add user preferences

Revision ID: 99f0e1d2c3b4
Revises: 66c1710f4924
Create Date: 2026-10-23 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '99f0e1d2c3b4'
down_revision: Union[str, Sequence[str], None] = '66c1710f4924'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'user_preferences' not in tables:
        op.create_table(
            'user_preferences',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('state', sa.String(), nullable=True),
            sa.Column('district', sa.String(), nullable=True),
            sa.Column('city', sa.String(), nullable=True),
            sa.Column('locality', sa.String(), nullable=True),
            sa.Column('property_types', sa.JSON(), nullable=True),
            sa.Column('min_reserve_price', sa.Numeric(), nullable=True),
            sa.Column('max_reserve_price', sa.Numeric(), nullable=True),
            sa.Column('preferred_banks', sa.JSON(), nullable=True),
            sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
        op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'user_preferences' in insp.get_table_names():
        indexes = {ix['name'] for ix in insp.get_indexes('user_preferences')}
        if 'ix_user_preferences_user_id' in indexes:
            op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
        op.drop_table('user_preferences')
