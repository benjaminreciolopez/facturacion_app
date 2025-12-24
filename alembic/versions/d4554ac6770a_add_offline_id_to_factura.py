from alembic import op
import sqlalchemy as sa


revision = 'xxxx'
down_revision = 'c9a971728bae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1️⃣ verificar si columna ya existe
    cols = conn.exec_driver_sql(
        "PRAGMA table_info(factura);"
    ).fetchall()

    colnames = [c[1] for c in cols]

    if "offline_id" not in colnames:
        op.add_column(
            "factura",
            sa.Column("offline_id", sa.String(), nullable=True)
        )

    # 2️⃣ crear índice si no existe
    res = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_factura_offline_id';"
    ).fetchone()

    if not res:
        op.create_index(
            "ix_factura_offline_id",
            "factura",
            ["offline_id"],
            unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()

    res = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_factura_offline_id';"
    ).fetchone()

    if res:
        op.drop_index("ix_factura_offline_id", table_name="factura")

    cols = conn.exec_driver_sql(
        "PRAGMA table_info(factura);"
    ).fetchall()

    colnames = [c[1] for c in cols]

    if "offline_id" in colnames:
        op.drop_column("factura", "offline_id")
