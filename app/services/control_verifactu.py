from fastapi import HTTPException, Request
from sqlmodel import Session, select
from datetime import datetime
import json
from hashlib import sha256

from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.factura import Factura, RegistroVerifactu
from app.models.emisor import Emisor
from app.services.verifactu_envio import enviar_a_aeat


# ============================================================
# CONFIG
# ============================================================

def get_config(session: Session, *, empresa_id: int) -> ConfiguracionSistema:
    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    if not config:
        raise HTTPException(
            500, "Configuración del sistema no inicializada."
        )

    return config


# ============================================================
# VALIDACIÓN PRINCIPAL VERI*FACTU
# ============================================================

def verificar_verifactu(factura: Factura, session: Session):

    empresa_id = factura.empresa_id
    if not empresa_id:
        raise HTTPException(400, "Factura sin empresa asociada")

    config = get_config(session, empresa_id=empresa_id)

    # Si VeriFactu no está activo → salimos
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

    # Emisor de la empresa
    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor or not emisor.nif:
        raise HTTPException(500, "No hay NIF de emisor configurado.")

    fecha_generacion = datetime.utcnow()

    hash_anterior = obtener_hash_anterior(session, empresa_id)

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
        empresa_id=empresa_id,
    )

    session.add(registro)

    # Envío real / mock
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
# HASH
# ============================================================

def generar_hash_verifactu(
    factura: Factura,
    nif_emisor: str,
    fecha_generacion: datetime,
    hash_anterior: str | None,
) -> str:

    if not factura.numero:
        raise ValueError("No se puede generar hash sin número definitivo.")

    if not factura.fecha:
        raise ValueError("No se puede generar hash sin fecha.")

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

    canonico = json.dumps(
        payload_hash,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return sha256(canonico).hexdigest()


# ============================================================
# HASH CADENA
# ============================================================

def obtener_hash_anterior(session: Session, empresa_id: int) -> str | None:
    ultimo = session.exec(
        select(RegistroVerifactu)
        .where(RegistroVerifactu.empresa_id == empresa_id)
        .order_by(RegistroVerifactu.fecha_registro.desc())
    ).first()

    return ultimo.hash_actual if ultimo else None
