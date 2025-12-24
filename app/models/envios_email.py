from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Session
from app.db.session import engine


class EnviosEmail(SQLModel, table=True):
    __tablename__ = "envios_email"

    id: Optional[int] = Field(default=None, primary_key=True)
    factura_id: int = Field(foreign_key="factura.id")
    destinatario: str
    cc: Optional[str] = None
    asunto: str
    cuerpo: Optional[str] = None
    adjunto_pdf: bool = Field(default=True)
    enviado_en: datetime = Field(default_factory=datetime.utcnow)
    estado: str = Field(default="OK")
    error: Optional[str] = None


def registrar_envio_email(
    factura_id: int,
    destinatario: str,
    asunto: str,
    cuerpo: Optional[str],
    cc: Optional[str],
    adjunto_pdf: bool,
    estado: str = "OK",
    error: Optional[str] = None,
):
    envio = EnviosEmail(
        factura_id=factura_id,
        destinatario=destinatario,
        cc=cc,
        asunto=asunto,
        cuerpo=cuerpo,
        adjunto_pdf=adjunto_pdf,
        estado=estado,
        error=error,
    )
    with Session(engine) as session:
        session.add(envio)
        session.commit()
        session.refresh(envio)

    return envio
