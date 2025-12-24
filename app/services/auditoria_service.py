from __future__ import annotations
from datetime import datetime
from sqlmodel import Session

from app.models.auditoria import Auditoria
from app.models.configuracion_sistema import ConfiguracionSistema


def auditar(
    session: Session,
    *,
    entidad: str,
    accion: str,
    resultado: str,
    entidad_id: int | None = None,
    nivel_evento: str | None = None,
    motivo: str | None = None,
    usuario: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
):
    """
    Registra un evento de auditoría según la configuración del sistema.
    """

    # Configuración singleton
    config = session.get(ConfiguracionSistema, 1)

    # =========================
    # 1) Auditoría desactivada
    # =========================
    if not config or not config.auditoria_activa:
        return

    # =========================
    # 2) Nivel de auditoría
    # =========================
    if config.nivel_auditoria == "BASICA":
        # En básica solo guardamos errores y bloqueos
        if resultado not in ("ERROR", "BLOQUEADO"):
            return

    # =========================
    # 3) Registrar evento
    # =========================
    evento = Auditoria(
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        resultado=resultado,
        motivo=motivo,
        usuario=usuario,
        ip=ip,
        user_agent=user_agent,
        fecha=datetime.utcnow(),
    )

    session.add(evento)
    session.commit()
