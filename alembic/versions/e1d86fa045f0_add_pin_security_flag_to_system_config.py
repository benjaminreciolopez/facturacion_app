"""Add PIN security flag to system config

Revision ID: a5bec6b5f5f7
Revises: a5bec6b5f5f7
Create Date: 2025-12-21 17:44:11.590788

"""
from alembic import op
import sqlalchemy as sa


revision = "add_pin_flag"
down_revision = "a5bec6b5f5f7"  # ⚠️ cambia esto por tu última revision real
branch_labels = None
depends_on = None


def column_exists(conn, table, column):
    rows = conn.exec_driver_sql(
        f"PRAGMA table_info({table});"
    ).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # Ajusta el nombre EXACTO si tu columna se llama distinto
    column_name = "seguridad_pin_enabled"

    if not column_exists(conn, "configuracionsistema", column_name):
        op.add_column(
            "configuracionsistema",
            sa.Column(column_name, sa.Boolean(), nullable=False, server_default="0"),
        )

def downgrade():
    op.drop_column("configuracionsistema", "pin_habilitado")
