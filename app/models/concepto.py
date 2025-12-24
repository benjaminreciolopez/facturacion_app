# app/models/concepto.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from app.models.linea_factura import LineaFactura

class Concepto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    descripcion: Optional[str] = ""
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)
    activo: bool = Field(default=True)

    # Relación con líneas de factura
    lineas: List["LineaFactura"] = Relationship(back_populates="concepto")
