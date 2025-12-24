# app/services/verifactu_envio.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException
from sqlmodel import Session

from app.models.factura import Factura, RegistroVerifactu
from app.models.emisor import Emisor
from app.models.configuracion_sistema import ConfiguracionSistema


# ============================================================
# RESULTADO
# ============================================================

@dataclass
class ResultadoEnvio:
    ok: bool
    http_status: int | None = None
    respuesta_texto: str | None = None
    error: str | None = None


# ============================================================
# ENDPOINTS (placeholders)
# ============================================================
# Nota: aquí NO inventamos rutas oficiales. Deja estos endpoints en ConfiguracionSistema
# (p.ej. verifactu_endpoint_pruebas / verifactu_endpoint_produccion) o ajusta aquí.
def _get_endpoint(config: ConfiguracionSistema) -> str:
    if not config.verifactu_url:
        raise HTTPException(500, "No hay endpoint VeriFactu configurado.")
    return config.verifactu_url


# ============================================================
# PAYLOAD (mínimo, extensible)
# ============================================================

def construir_payload_verifactu(
    factura: Factura,
    emisor: Emisor,
    registro: RegistroVerifactu,
    config: ConfiguracionSistema,
) -> Dict[str, Any]:

    # ---------------------------
    # Totales coherentes con tu modelo
    # ---------------------------

    base_imponible = float(factura.subtotal or 0.0)
    iva_total = float(factura.iva_total or 0.0)
    total = float(factura.total or 0.0)

    iva_items = []

    # Si el sistema actualmente usa IVA global
    if factura.iva_global and factura.iva_global > 0:
        iva_items.append({
            "tipo": float(factura.iva_global),
            "base": round(base_imponible, 2),
            "cuota": round(iva_total, 2),
        })

    # Si no hay IVA → reflejarlo igualmente
    else:
        iva_items.append({
            "tipo": 0.0,
            "base": round(base_imponible, 2),
            "cuota": 0.0,
        })

    totales = {
        "base_imponible": round(base_imponible, 2),
        "iva": iva_items,
        "total": round(total, 2),
    }

    # ---------------------------
    # Cliente
    # ---------------------------
    cliente_dict = {}
    if factura.cliente:
        cliente_dict = {
            "nombre": factura.cliente.nombre or "",
            "nif": factura.cliente.nif or "",
        }

    return {
        "modo": config.verifactu_modo,
        "emisor": {
            "nif": (emisor.nif or "").upper(),
            "nombre": getattr(emisor, "nombre", "") or "",
        },
        "factura": {
            "id": factura.id,
            "numero": factura.numero or "",
            "fecha": factura.fecha.isoformat(),
            "cliente": cliente_dict,
            "totales": totales,
        },
        "encadenado": {
            "hash_actual": registro.hash_actual,
            "hash_anterior": registro.hash_anterior or "",
            "fecha_registro_utc": registro.fecha_registro.isoformat(),
        },
    }


# ============================================================
# ENVÍO (TEST simulado / PROD HTTP)
# ============================================================

def enviar_a_aeat(
    *,
    factura: Factura,
    emisor: Emisor,
    registro: RegistroVerifactu,
    config: ConfiguracionSistema,
    session: Session,
) -> ResultadoEnvio:

    # --- Validaciones mínimas ---
    if not emisor or not emisor.nif:
        raise HTTPException(500, "No hay NIF de emisor para envío Veri*Factu.")

    if not factura.numero or not factura.fecha:
        raise HTTPException(500, "Factura sin número/fecha definitiva para envío Veri*Factu.")

    if registro is None or not registro.hash_actual:
        raise HTTPException(500, "Registro Veri*Factu inválido (sin hash).")

    # asegurar fecha de registro
    if not getattr(registro, "fecha_registro", None):
        registro.fecha_registro = datetime.utcnow()
        session.add(registro)
        session.commit()

    endpoint = _get_endpoint(config)
    payload = construir_payload_verifactu(factura, emisor, registro, config)

    try:
        timeout = httpx.Timeout(20.0, connect=10.0)

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        # ------------- RESPUESTA CORRECTA -----------------
        if 200 <= resp.status_code < 300:
            registro.estado_envio = "ENVIADO"
            registro.error_envio = None
            session.add(registro)
            session.commit()

            return ResultadoEnvio(
                ok=True,
                http_status=resp.status_code,
                respuesta_texto=resp.text[:2000],
            )

        # ------------- ERROR HTTP -----------------
        registro.estado_envio = "ERROR"
        registro.error_envio = f"HTTP {resp.status_code}: {resp.text[:500]}"
        session.add(registro)
        session.commit()

        return ResultadoEnvio(
            ok=False,
            http_status=resp.status_code,
            respuesta_texto=resp.text[:2000],
            error=registro.error_envio,
        )

    except Exception as e:
        registro.estado_envio = "ERROR"
        registro.error_envio = str(e)[:500]
        session.add(registro)
        session.commit()

        return ResultadoEnvio(
            ok=False,
            http_status=None,
            respuesta_texto=None,
            error=str(e),
        )
