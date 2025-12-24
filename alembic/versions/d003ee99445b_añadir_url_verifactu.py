"""Añadir URL VeriFactu

Revision ID: d003ee99445b
Revises: adc85ba467aa
Create Date: 2025-12-18 19:36:27.748624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd003ee99445b'
down_revision: Union[str, Sequence[str], None] = 'adc85ba467aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
