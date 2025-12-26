from datetime import date
from fastapi import HTTPException, Request
from sqlmodel import select, Session

from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.factura import Factura


# =====================================================
# CONFIGURACIÓN DEL SISTEMA
# =====================================================

def get_config(
    session: Session,
    request: Request | None = None,
    empresa_id: int | None = None,
) -> ConfiguracionSistema:
    """
    Obtiene la configuración del sistema respetando multiempresa.
    Permite:
        - request.session["empresa_id"]
        - empresa_id directo (background / jobs)
    """

    # ---------------------------
    # Resolver empresa
    # ---------------------------
    if empresa_id is None and request:
        empresa_id = request.session.get("empresa_id")

    if empresa_id is None:
        raise HTTPException(
            status_code=401,
            detail="Empresa no seleccionada en sesión"
        )

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    if not config:
        raise HTTPException(
            status_code=500,
            detail="Configuración del sistema no inicializada."
        )

    return config


# =====================================================
# BLOQUEOS NORMATIVOS SOBRE FACTURAS
# =====================================================

def bloquear_edicion_factura(factura: Factura, session: Session, request: Request | None = None):
    """
    Impide la edición de facturas validadas si el sistema
    está configurado como inmutable.
    """
    config = get_config(session, request=request, empresa_id=factura.empresa_id)

    if config.facturas_inmutables and factura.estado == "VALIDADA":
        raise HTTPException(
            status_code=403,
            detail="Las facturas validadas son inmutables según la configuración del sistema."
        )


def bloquear_borrado_factura(factura: Factura, session: Session, request: Request | None = None):
    """
    Impide el borrado de facturas validadas si está prohibido
    por configuración.
    """
    config = get_config(session, request=request, empresa_id=factura.empresa_id)

    if config.prohibir_borrado_facturas and factura.estado == "VALIDADA":
        raise HTTPException(
            status_code=403,
            detail="No se permite borrar facturas validadas."
        )


def validar_fecha_factura(fecha: date, session: Session, request: Request | None = None, empresa_id: int | None = None):
    """
    Verifica si se permiten fechas pasadas en facturación.
    """
    config = get_config(session, request=request, empresa_id=empresa_id)

    if config.bloquear_fechas_pasadas and fecha < date.today():
        raise HTTPException(
            status_code=403,
            detail="No se permiten fechas pasadas según la configuración del sistema."
        )
