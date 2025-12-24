from fastapi import HTTPException
from sqlmodel import Session, select
from datetime import datetime
from hashlib import sha256

from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.factura import Factura, RegistroVerifactu
from app.models.emisor import Emisor
from app.services.verifactu_envio import enviar_a_aeat


# ============================================================
# UTILIDAD
# ============================================================

def get_config(session: Session) -> ConfiguracionSistema:
    config = session.get(ConfiguracionSistema, 1)
    if not config:
        raise HTTPException(
            status_code=500,
            detail="Configuración del sistema no inicializada."
        )
    return config


# ============================================================
# VALIDACIÓN PRINCIPAL VERI*FACTU
# ============================================================

def verificar_verifactu(factura: Factura, session: Session):

    config = get_config(session)

    if not config.verifactu_activo or config.verifactu_modo == "OFF":
        return

    if factura.estado != "BORRADOR":
        raise HTTPException(
            403,
            "Solo se pueden enviar a Veri*Factu facturas en estado BORRADOR."
        )

    if not factura.fecha:
        raise HTTPException(400, "La factura debe tener fecha.")

    if factura.total is None:
        raise HTTPException(400, "La factura no tiene total.")

    emisor = session.get(Emisor, 1)
    if not emisor or not emisor.nif:
        raise HTTPException(
            500,
            "No hay NIF de emisor configurado."
        )

    fecha_generacion = datetime.utcnow()
    hash_anterior = obtener_hash_anterior(session)

    nuevo_hash = generar_hash_verifactu(
        factura=factura,
        nif_emisor=emisor.nif,
        fecha_generacion=fecha_generacion,
        hash_anterior=hash_anterior,
    )

    registro = RegistroVerifactu(
        factura_id=factura.id,
        numero_factura=factura.numero,
        fecha_factura=factura.fecha,
        total_factura=factura.total,
        hash_actual=nuevo_hash,
        hash_anterior=hash_anterior,
        fecha_registro=fecha_generacion,
        estado_envio="PENDIENTE",
    )

    session.add(registro)

    enviar_a_aeat(
        factura=factura,
        emisor=emisor,
        registro=registro,
        config=config,
        session=session,
    )

    factura.verifactu_hash = nuevo_hash
    factura.verifactu_fecha_generacion = fecha_generacion

    config.verifactu_ultimo_hash = nuevo_hash
    config.verifactu_ultimo_envio = fecha_generacion

    session.add(factura)
    session.add(config)
    session.commit()


# ============================================================
# HASH VERI*FACTU
# ============================================================

import json
from hashlib import sha256

def generar_hash_verifactu(
    factura: Factura,
    nif_emisor: str,
    fecha_generacion: datetime,
    hash_anterior: str | None,
) -> str:
    """
    Hash encadenado VeriFactu basado en contenido completo.
    El hash depende de la factura REAL, no solo de 4 campos.
    """

    if not factura.numero:
        raise ValueError("No se puede generar hash sin número definitivo.")

    if not factura.fecha:
        raise ValueError("No se puede generar hash sin fecha.")

    # -------------------------
    # Construimos estructura estable
    # -------------------------
    payload_hash = {
        "emisor": {
            "nif": nif_emisor.strip().upper(),
        },
        "factura": {
            "numero": factura.numero.strip(),
            "fecha": factura.fecha.isoformat()[:10],
            "total": float(factura.total or 0.0),
        },
        "registro": {
            "fecha_registro_utc": fecha_generacion.isoformat(),
            "hash_anterior": hash_anterior or "",
        },
    }

    # Si tienes desglose de IVA, inclúyelo aquí
    if hasattr(factura, "detalle_iva") and factura.detalle_iva:
        payload_hash["factura"]["iva"] = [
            {
                "tipo": float(li.tipo_iva),
                "base": float(li.base),
                "cuota": float(li.cuota),
            }
            for li in factura.detalle_iva
        ]

    # -------------------------
    # JSON CANÓNICO
    # -------------------------
    canonico = json.dumps(
        payload_hash,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return sha256(canonico).hexdigest()

# ============================================================
# REGISTRO SIMULADO
# ============================================================

def registrar_envio_simulado(config: ConfiguracionSistema, hash_envio: str):
    """
    Placeholder de envío Veri*Factu.
    Sirve para TEST y como base de auditoría.
    """
    # Aquí en el futuro:
    # - guardar log
    # - guardar payload enviado
    # - guardar respuesta AEAT
    pass


def obtener_hash_anterior(session: Session) -> str | None:
    ultimo = session.exec(
        select(RegistroVerifactu)
        .order_by(RegistroVerifactu.fecha_registro.desc())
    ).first()

    return ultimo.hash_actual if ultimo else None

