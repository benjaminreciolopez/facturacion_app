# app/services/decoradores_factura.py

from functools import wraps
from fastapi import HTTPException, Request
from sqlmodel import Session, select

from app.models.factura import Factura
from app.models.configuracion_sistema import ConfiguracionSistema
from app.services.auditoria_service import auditar


def bloquear_si_factura_inmutable(
    *,
    allow_borrador: bool = True,
):
    """
    Decorador para bloquear acciones sobre facturas inmutables.

    Reglas:
    - Si factura tiene hash Veri*Factu → BLOQUEO ABSOLUTO
    - Si config.facturas_inmutables y estado != BORRADOR → BLOQUEO
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            # =========================
            # Obtener dependencias
            # =========================
            session: Session = kwargs.get("session")
            factura_id = kwargs.get("factura_id")
            request: Request = kwargs.get("request")

            if not session or factura_id is None:
                raise RuntimeError(
                    "El decorador requiere 'session' y 'factura_id' en la función."
                )

            factura = session.get(Factura, factura_id)
            if not factura:
                raise HTTPException(404, "Factura no encontrada.")

            empresa_id = factura.empresa_id

            config = session.exec(
                select(ConfiguracionSistema).where(
                    ConfiguracionSistema.empresa_id == empresa_id
                )
            ).first()

            if not config:
                raise HTTPException(
                    500,
                    "Configuración del sistema no inicializada."
                )

            # ======================================================
            # 🔒 BLOQUEO POR CONFIGURACIÓN
            # ======================================================
            if config.facturas_inmutables and factura.estado != "BORRADOR":
                raise HTTPException(
                    403,
                    "Factura validada: modificaciones no permitidas."
                )

            # ======================================================
            # 🔒 BLOQUEO ABSOLUTO VERI*FACTU + AUDITORÍA
            # ======================================================
            if factura.verifactu_hash:
                try:
                    auditar(
                        request=request,
                        session=session,
                        entidad="FACTURA",
                        entidad_id=factura.id,
                        accion=func.__name__,
                        resultado="BLOQUEADO",
                        nivel_evento="FISCAL",
                        motivo="Factura protegida por Veri*Factu",
                    )
                except Exception:
                    # Auditoría nunca debe romper lógica funcional
                    pass

                raise HTTPException(
                    403,
                    "Factura bloqueada legalmente (Veri*Factu)."
                )

            # ======================================================
            # 🔒 Si se exige NO permitir BORRADOR
            # ======================================================
            if not allow_borrador and factura.estado == "BORRADOR":
                raise HTTPException(
                    403,
                    "Operación no permitida sobre facturas en borrador."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator
