"""add sys_var table

Revision ID: 9e4a6f7b8c1d
Revises: c8f2d6c4a8aa
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9e4a6f7b8c1d'
down_revision: Union[str, Sequence[str], None] = 'c8f2d6c4a8aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'sys_var',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('sys_var')