from datetime import date
from fastapi import HTTPException
from sqlmodel import Session

from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.factura import Factura


# =====================================================
# CONFIGURACIÓN DEL SISTEMA
# =====================================================

def get_config(session: Session) -> ConfiguracionSistema:
    """
    Devuelve la configuración global del sistema.
    Debe existir siempre el registro con ID=1.
    """
    config = session.get(ConfiguracionSistema, 1)
    if not config:
        raise HTTPException(
            status_code=500,
            detail="Configuración del sistema no inicializada."
        )
    return config


# =====================================================
# BLOQUEOS NORMATIVOS SOBRE FACTURAS
# =====================================================

def bloquear_edicion_factura(factura: Factura, session: Session):
    """
    Impide la edición de facturas validadas si el sistema
    está configurado como inmutable.
    """
    config = get_config(session)

    if config.facturas_inmutables and factura.estado == "VALIDADA":
        raise HTTPException(
            status_code=403,
            detail=(
                "Las facturas validadas son inmutables según la "
                "configuración del sistema."
            )
        )


def bloquear_borrado_factura(factura: Factura, session: Session):
    """
    Impide el borrado de facturas validadas si está prohibido
    por configuración.
    """
    config = get_config(session)

    if config.prohibir_borrado_facturas and factura.estado == "VALIDADA":
        raise HTTPException(
            status_code=403,
            detail="No se permite borrar facturas validadas."
        )


def validar_fecha_factura(fecha: date, session: Session):
    """
    Verifica si se permiten fechas pasadas en facturación.
    """
    config = get_config(session)

    if config.bloquear_fechas_pasadas and fecha < date.today():
        raise HTTPException(
            status_code=403,
            detail=(
                "No se permiten fechas pasadas según la "
                "configuración del sistema."
            )
        )
