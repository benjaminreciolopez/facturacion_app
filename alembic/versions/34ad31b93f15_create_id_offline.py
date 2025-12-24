"""create id offline

Revision ID: 34ad31b93f15
Revises: 52638c854089
Create Date: 2025-12-24 17:16:39.348284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34ad31b93f15'
down_revision: Union[str, Sequence[str], None] = '52638c854089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(conn, table, column):
    rows = conn.exec_driver_sql(
        f"PRAGMA table_info({table});"
    ).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # Si NO existe → la creamos
    if not column_exists(conn, "factura", "offline_id"):
        op.add_column(
            "factura",
            sa.Column("offline_id", sa.String(), nullable=True),
        )

        op.create_index(
            "ix_factura_offline_id",
            "factura",
            ["offline_id"],
            unique=False
        )

def downgrade() -> None:
    with op.batch_alter_table("factura") as batch_op:
        batch_op.drop_index("ix_factura_offline_id")
        batch_op.drop_column("offline_id")
