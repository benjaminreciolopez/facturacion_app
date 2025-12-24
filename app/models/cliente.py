from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import UniqueConstraint

if TYPE_CHECKING:
    from app.models.factura import Factura


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"

    __table_args__ = (
        UniqueConstraint("nif", name="uq_cliente_nif"),
        UniqueConstraint("email", name="uq_cliente_email"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(foreign_key="empresa.id")

    nombre: str
    nif: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None

    direccion: Optional[str] = None
    poblacion: Optional[str] = None
    cp: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = "España"

    activo: bool = True
    fecha_alta: datetime = Field(default_factory=datetime.utcnow)

    # relación 1-N con Factura
    facturas: List["Factura"] = Relationship(back_populates="cliente")
