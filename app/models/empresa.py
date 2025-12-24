from sqlmodel import SQLModel, Field
from typing import Optional


class Empresa(SQLModel, table=True):
    __tablename__ = "empresa"

    id: Optional[int] = Field(default=None, primary_key=True)

    nombre: str = Field(index=True)
    cif: str | None = Field(default=None, index=True, unique=True)
    activa: bool = Field(default=True)
