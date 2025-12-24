from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv
from sqlmodel import SQLModel

# Cargar variables de entorno
load_dotenv(".env.dev")

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# IMPORTANTE:
# Importa TODOS los modelos para que SQLModel registre las tablas
# Ajusta estos imports a tu estructura real
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.factura import Factura
from app.models.linea_factura import LineaFactura
from app.models.iva import IVA
from app.models.user import User
from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.auditoria import Auditoria
from app.models.empresa import Empresa
from app.models.password_reset import PasswordReset

# añade aquí otros modelos si existen

target_metadata = SQLModel.metadata


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está definida")
    return database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    config.set_main_option("sqlalchemy.url", get_database_url())

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
