"""Add table envios_email

Revision ID: 52638c854089
Revises: add_pin_flag
Create Date: 2025-12-21 19:33:11.258736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52638c854089'
down_revision: Union[str, Sequence[str], None] = 'c9a971728bae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
