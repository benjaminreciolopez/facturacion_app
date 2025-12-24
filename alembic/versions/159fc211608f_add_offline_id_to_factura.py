"""add offline_id to factura

Revision ID: 159fc211608f
Revises: e2ed857a3325
Create Date: 2025-12-24 17:39:24.836452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '159fc211608f'
down_revision: Union[str, Sequence[str], None] = 'e2ed857a3325'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(conn, table, column):
    rows = conn.exec_driver_sql(
        f"PRAGMA table_info({table});"
    ).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # Si ya existe → NO hacemos nada
    if column_exists(conn, "factura", "offline_id"):
        return

    op.add_column(
        "factura",
        sa.Column("offline_id", sa.String(), nullable=True),
    )

    op.create_index(
        "ix_factura_offline_id",
        "factura",
        ["offline_id"],
        unique=False,
    )


def downgrade() -> None:
    pass