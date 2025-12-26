from datetime import date
from sqlmodel import Session, select
from fastapi import HTTPException
from app.models.factura import Factura
from app.models.emisor import Emisor
from app.models.linea_factura import LineaFactura
from app.models.emisor import Emisor
import re


def generar_numero_factura(session: Session, fecha: date, empresa_id: int) -> str:
    
    emisor = session.exec(
            select(Emisor).where(Emisor.empresa_id == empresa_id)
        ).first()    
    if not emisor:
        raise HTTPException(400, "No hay emisor configurado para esta empresa")

    year = fecha.year

    # Reiniciar correlativo al cambiar de año
    if emisor.ultimo_anio_numerado != year:
        emisor.siguiente_numero = 1
        emisor.ultimo_anio_numerado = year
        session.add(emisor)
        session.commit()

    correlativo = emisor.siguiente_numero
    plantilla = emisor.numeracion_plantilla

    # ----------------------------------------------------
    # Procesar {NUM:0Nd}
    # ----------------------------------------------------

    def repl_num(match):
        formato = match.group(1)  # Ejemplo: "04d"
        ancho = int(formato[:-1])  # quitar la "d" final
        return f"{correlativo:0{ancho}d}"

    # Reemplazo flexible para {NUM:0Nd}
    numero = re.sub(r"\{NUM:(0\d+)d\}", repl_num, plantilla)

    # Reemplazo simple {NUMERO}
    numero = numero.replace("{NUMERO}", str(correlativo))

    # Reemplazo variables restantes
    numero = numero.replace("{SERIE}", emisor.serie_facturacion or "")
    numero = numero.replace("{AÑO}", str(year))
    numero = numero.replace("{MES}", f"{fecha.month:02d}")

    # Incrementar correlativo
    emisor.siguiente_numero + 1
    session.add(emisor)
    session.commit()

    return numero


def bloquear_numeracion(session: Session, fecha: date, empresa_id: int):
    """
    Se ejecuta automáticamente al validar la primera factura del año.
    Bloquea el modo de numeración hasta el año siguiente.
    """

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()
    if not emisor:
        raise HTTPException(400, "No hay emisor configurado para esta empresa")
    
    year = fecha.year

    if (
            emisor.numeracion_bloqueada
            and emisor.anio_numeracion_bloqueada == year
        ):
            return

    emisor.numeracion_bloqueada = True
    emisor.anio_numeracion_bloqueada = year

    session.add(emisor)
    session.commit()


def recalcular_totales(factura: Factura, lineas: list[LineaFactura]):
    subtotal = 0.0

    for l in lineas:
        base = l.cantidad * l.precio_unitario
        subtotal += base
        l.total = base

    factura.subtotal = round(subtotal, 2)

    iva_percent = factura.iva_global or 0.0
    factura.iva_total = round(subtotal * (iva_percent / 100), 2)

    factura.total = round(factura.subtotal + factura.iva_total, 2)

    return factura

def generar_mensaje_rectificativa(factura, emisor):
    """
    Genera un texto legal completo para facturas rectificativas.
    - Si el emisor configuró un texto, se usa como base.
    - Siempre se añaden los datos legales obligatorios.
    """

    base = (emisor.texto_rectificativa or "").strip()

    # Si el usuario no escribió nada → mensaje completo por defecto
    if not base:
        base = "Factura rectificativa emitida conforme al Art. 89 de la Ley 37/1992 del IVA."

    detalle = (
        f" Esta rectificación afecta a la factura original Nº {factura.numero} "
        f"de fecha {factura.fecha.strftime('%d/%m/%Y')}, dejando sin efecto sus importes."
    )

    return base + detalle
