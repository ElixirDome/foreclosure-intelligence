"""Create the original users and properties tables.

Revision ID: 0a1b2c3d4e5f
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "properties",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Numeric(), nullable=True),
        sa.Column("area_sqft", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["userid"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("properties")
    op.drop_table("users")
