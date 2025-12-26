# app/models/iva.py
from sqlmodel import SQLModel, Field
from typing import Optional

class IVA(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int | None = Field(default=None, foreign_key="empresa.id")
    porcentaje: float                       # 21, 10, 4, 0...
    descripcion: Optional[str] = None       # “General”, “Reducido”, etc.
    activo: bool = True
