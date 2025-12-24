# app/services/verifactu_qr.py
from __future__ import annotations

from urllib.parse import quote
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.models.factura import Factura
from app.models.emisor import Emisor
from app.models.configuracion_sistema import ConfiguracionSistema


def _fmt_fecha_qr(d: date) -> str:
    # DD-MM-AAAA (obligatorio)
    return d.strftime("%d-%m-%Y")


def _fmt_importe_qr(total) -> str:
    # Punto decimal y sin separador de miles. Mejor asegurar 2 decimales.
    dec = Decimal(str(total or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(dec, "f")  # "241.40"


def construir_url_qr(
    factura: Factura,
    emisor: Emisor,
    config: ConfiguracionSistema,
    *,
    entorno: str = "PRODUCCION",      # "PRUEBAS" | "PRODUCCION"
    
    es_verifactu: bool = True,        # True => ValidarQR ; False => ValidarQRNoVerifactu
) -> str:
    """
    Construye la URL exacta para el QR (AEAT).
    Param obligatorios: nif, numserie, fecha (DD-MM-AAAA), importe.
    """

    if not emisor or not emisor.nif:
        raise ValueError("Emisor sin NIF. Necesario para el QR.")
    if not factura or not factura.numero:
        raise ValueError("Factura sin número. El QR requiere numserie.")
    if not factura.fecha:
        raise ValueError("Factura sin fecha. El QR requiere fecha.")
    if factura.total is None:
        raise ValueError("Factura sin total. El QR requiere importe.")

    nif = emisor.nif.strip().upper()

    # numserie = "Nº serie + Nº factura" (en tu caso ya lo guardas como factura.numero)
    # OJO: puede contener caracteres especiales; hay que URL-encode.
    numserie = quote((factura.numero or "").strip(), safe="")  # ASCII 32-126 según doc

    fecha = _fmt_fecha_qr(factura.fecha)
    importe = _fmt_importe_qr(factura.total)

    if entorno.upper() == "PRUEBAS":
        base_veri = "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
        base_noveri = "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu"
    else:
        base_veri = "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"
        base_noveri = "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu"

    base = base_veri if es_verifactu else base_noveri

    return f"{base}?nif={nif}&numserie={numserie}&fecha={fecha}&importe={importe}"
