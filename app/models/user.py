from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    email: str = Field(index=True, unique=True)
    password_hash: str

    nombre: str | None = None
    rol: str = "user"  # admin | user
    activo: bool = True

    empresa_id: int = Field(foreign_key="empresa.id")
    pin_hash: Optional[str] = None
    requiere_reset: bool = False
    creado: datetime = Field(default_factory=datetime.utcnow)
