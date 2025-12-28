from __future__ import annotations
from datetime import datetime
from sqlmodel import Session, select
from fastapi import Request

from app.models.auditoria import Auditoria
from app.models.configuracion_sistema import ConfiguracionSistema


def auditar(
    session: Session,
    *,
    entidad: str,
    accion: str,
    resultado: str,
    entidad_id: int | None = None,
    motivo: str | None = None,
    usuario: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request: Request | None = None,
    empresa_id: int | None = None,
    payload: dict | None = None,
):
    """
    Registra un evento de auditoría de forma segura.
    NUNCA debe romper la ejecución del sistema.
    """

    try:
        # =========================
        # 1) Resolver empresa_id
        # =========================
        if empresa_id is None and request:
            empresa_id = request.session.get("empresa_id")

        if empresa_id is None:
            # Si no sabemos empresa → no auditamos
            return

        # =========================
        # 2) Leer configuración
        # =========================
        config = session.exec(
            select(ConfiguracionSistema).where(
                ConfiguracionSistema.empresa_id == empresa_id
            )
        ).first()

        if not config or not config.auditoria_activa:
            return

        # =========================
        # 3) Nivel de auditoría
        # =========================
        if config.nivel_auditoria == "BASICA":
            if resultado not in ("ERROR", "BLOQUEADO"):
                return

        # =========================
        # 4) Registrar evento
        # =========================
        evento = Auditoria(
            entidad=entidad,
            entidad_id=entidad_id,
            accion=accion,
            resultado=resultado,
            motivo=motivo,
            user_id=usuario,
            company_id=empresa_id,
            ip=ip,
            user_agent=user_agent,
            payload=payload,
            created_at=datetime.utcnow(),   # << CORRECTO
        )

        session.add(evento)
        session.commit()

    except Exception:
        try:
            session.rollback()
        except:
            pass
        return
