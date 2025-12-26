from alembic import op
import sqlalchemy as sa


# revision identifiers…
revision = "8046cce9854a"
down_revision = "9f6b954fc017"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info(iva);"))]

    # Solo añadir si no existe
    if "empresa_id" not in cols:
        with op.batch_alter_table("iva") as batch_op:
            batch_op.add_column(
                sa.Column("empresa_id", sa.Integer(), nullable=True)
            )
        # Opcional: asignar empresa 1 por defecto
        conn.execute(sa.text("UPDATE iva SET empresa_id = 1 WHERE empresa_id IS NULL"))


def downgrade():
    conn = op.get_bind()
    cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info(iva);"))]

    if "empresa_id" in cols:
        with op.batch_alter_table("iva") as batch_op:
            batch_op.drop_column("empresa_id")
