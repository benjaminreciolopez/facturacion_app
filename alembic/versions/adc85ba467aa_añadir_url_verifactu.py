"""Añadir URL VeriFactu

Revision ID: adc85ba467aa
Revises: faa59d1660b5
Create Date: 2025-12-18 19:31:11.322776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adc85ba467aa'
down_revision: Union[str, Sequence[str], None] = 'faa59d1660b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
