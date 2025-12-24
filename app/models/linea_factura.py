from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.factura import Factura
    from app.models.concepto import Concepto


class LineaFactura(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    factura_id: int = Field(foreign_key="factura.id")
    factura: Optional["Factura"] = Relationship(back_populates="lineas")

    concepto_id: Optional[int] = Field(default=None, foreign_key="concepto.id")
    concepto: Optional["Concepto"] = Relationship(back_populates="lineas")

    descripcion: str
    cantidad: float = 1.0
    precio_unitario: float = 0.0
    total: float = 0.0
