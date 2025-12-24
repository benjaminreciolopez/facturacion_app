"""creacion tablas usuario empresa passwordreset

Revision ID: c821d63187ac
Revises: 98df7a550919
Create Date: 2025-12-20 08:35:28.318768
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c821d63187ac"
down_revision: Union[str, Sequence[str], None] = "98df7a550919"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    from sqlalchemy import text

    conn = op.get_bind()

    # Evitar crear índice si ya existe (SQLite friendly)
    res = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_empresa_cif';"
    ).fetchone()

    if not res:
        op.create_index(
            op.f("ix_empresa_cif"),
            "empresa",
            ["cif"],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade schema."""

    # Eliminar solo lo que creamos arriba
    from sqlalchemy import text

    conn = op.get_bind()

    res = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_empresa_cif';"
    ).fetchone()

    if res:
        op.drop_index(op.f("ix_empresa_cif"), table_name="empresa")
