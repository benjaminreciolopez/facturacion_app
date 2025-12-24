from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, JSON


class Auditoria(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # Qué se toca
    entidad: str                     # FACTURA, VERIFACTU, CONFIG
    entidad_id: Optional[int]        # id de la entidad

    # Qué ocurre
    accion: str                      # VALIDAR, ANULAR, ENVIAR_AEAT
    resultado: str                   # OK | ERROR | BLOQUEADO

    # Contexto del resultado
    motivo: Optional[str]            # mensaje humano
    error_codigo: Optional[str]      # VALIDACION_FECHA, HASH_INVALIDO, etc.

    # Contexto de ejecución
    user_id: Optional[str]           # id externo (app180 / auth)
    company_id: Optional[int]        # empresa emisora
    origen: Optional[str]            # UI | API | SISTEMA

    # Datos técnicos
    ip: Optional[str]
    user_agent: Optional[str]

    # Contexto extra (NO lógica)
    payload: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON)
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
