"""Add empresa_id to registroverifactu

Revision ID: 33e899977cfb
Revises: 8046cce9854a
Create Date: 2025-12-28 20:05:19.699642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33e899977cfb'
down_revision: Union[str, Sequence[str], None] = '8046cce9854a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    #
    # 1️⃣ Comprobar si la columna ya existe
    #
    result = conn.execute(sa.text("PRAGMA table_info('registroverifactu')"))
    columns = [row[1] for row in result]   # row[1] = column name en SQLite

    # Si no existe → crearla y rellenar
    if "empresa_id" not in columns:
        op.add_column(
            "registroverifactu",
            sa.Column("empresa_id", sa.Integer(), nullable=True)
        )

        op.execute("""
            UPDATE registroverifactu
            SET empresa_id = (
                SELECT factura.empresa_id
                FROM factura
                WHERE factura.id = registroverifactu.factura_id
            )
            WHERE factura_id IS NOT NULL;
        """)

    #
    # 2️⃣ Aplicar restricciones correctamente
    #
    with op.batch_alter_table("registroverifactu", recreate="auto") as batch:
        batch.alter_column("empresa_id", nullable=False)
        batch.create_index(
            "ix_registroverifactu_empresa_id",
            ["empresa_id"]
        )
        batch.create_foreign_key(
            "fk_registroverifactu_empresa",
            "empresa",
            ["empresa_id"],
            ["id"],
            ondelete="CASCADE"
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_registroverifactu_empresa",
        "registroverifactu",
        type_="foreignkey"
    )
    op.drop_index("ix_registroverifactu_empresa_id", table_name="registroverifactu")
    op.drop_column("registroverifactu", "empresa_id")