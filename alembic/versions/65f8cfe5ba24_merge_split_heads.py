"""Merge split heads

Revision ID: 65f8cfe5ba24
Revises: 34ad31b93f15, xxxx
Create Date: 2025-12-24 17:26:10.683737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65f8cfe5ba24'
down_revision: Union[str, Sequence[str], None] = ('34ad31b93f15', 'xxxx')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
