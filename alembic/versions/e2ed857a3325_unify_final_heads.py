"""Unify final heads

Revision ID: e2ed857a3325
Revises: 65f8cfe5ba24, add_pin_flag
Create Date: 2025-12-24 17:38:08.469155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2ed857a3325'
down_revision: Union[str, Sequence[str], None] = ('65f8cfe5ba24', 'add_pin_flag')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
