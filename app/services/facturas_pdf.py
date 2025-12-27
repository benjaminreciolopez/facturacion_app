# app/services/facturas_pdf.py

import os
import textwrap
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm

from app.services.verifactu_qr import construir_url_qr
from app.models.configuracion_sistema import ConfiguracionSistema
from app.db.session import engine
from sqlmodel import Session
from app.services.paths import resolver_ruta_pdf
import os
from io import BytesIO

def generar_factura_pdf(
    factura,
    lineas,
    ruta_base,
    emisor,
    config: ConfiguracionSistema | None = None,
    incluir_mensaje_iva=True,
):

    en_render = (
        os.getenv("APP_ENV", "").lower() == "render" 
        or os.getenv("RENDER", "").lower() == "true"
    )

    # ============================================
    # PREPARACIÓN ENTORNO
    # ============================================
    if not factura:
        raise Exception("Factura no válida")

    fecha = getattr(factura, "fecha", None)
    if not fecha:
        raise Exception("La factura no tiene fecha asignada")

    numero = str(getattr(factura, "numero", "SIN_NUMERO")).strip()
    safe_num = numero.replace("/", "-").replace("\\", "-")

    # ============================================
    # CREAR CANVAS
    # ============================================
    if en_render:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        ruta_pdf = None
        ruta_url = None
    else:
        if not ruta_base:
            raise Exception("Ruta PDF no configurada en el emisor.")

        base_dir = resolver_ruta_pdf(ruta_base)

        año = str(fecha.year)
        trimestre = f"T{((fecha.month - 1) // 3) + 1}"

        carpeta_destino = os.path.join(base_dir, año, trimestre)
        os.makedirs(carpeta_destino, exist_ok=True)

        nombre_archivo = f"Factura_{safe_num}.pdf"
        ruta_pdf = os.path.join(carpeta_destino, nombre_archivo)



    # =============================
    # Crear PDF
    # =============================
    ancho, alto = A4
    margen_x = 30
    top_y = alto - 40

    # -----------------------------
    # TÍTULO CENTRADO
    # -----------------------------
    es_rectificativa = str(factura.numero).endswith("R")
    titulo = "FACTURA RECTIFICATIVA" if es_rectificativa else "FACTURA"

    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(ancho / 2, top_y, titulo)

    # =============================
    # MARCA VISUAL ENTORNO TEST
    # =============================
    if config and config.verifactu_modo == "TEST":
        c.setFont("Helvetica-Bold", 40)
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.saveState()
        c.translate(ancho / 2, alto / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "ENTORNO DE PRUEBAS")
        c.restoreState()
        c.setFillColorRGB(0, 0, 0)

    # =============================
    # LOGO + DATOS EMISOR (IZQUIERDA)
    # =============================
    # Fallback en caso de que emisor venga None
    if emisor is None:
        class Dummy:
            nombre = "Emisor"
            direccion = ""
            poblacion = ""
            cp = ""
            provincia = ""
            nif = ""
            telefono = ""
            email = ""
            texto_rectificativa = ""
            texto_pie = ""
            logo_path = None
            cuenta_bancaria = None

        emisor = Dummy()

    # Logo arriba-izquierda
    logo_y_top = alto - 50  # algo por debajo del título
    logo_x = margen_x
    y_emisor_inicio = logo_y_top  # por si no hay logo

    logo_path = getattr(emisor, "logo_path", None)
    if logo_path:
        # convertir /static/uploads/... a ruta real de disco si es el caso
        if logo_path.startswith("/"):
            logo_fs = os.path.join("app", logo_path.lstrip("/"))
        else:
            logo_fs = logo_path

        if os.path.exists(logo_fs):
            try:
                c.drawImage(logo_fs, logo_x, logo_y_top - 60, width=100, height=80, mask="auto")
                y_emisor_inicio = logo_y_top - 70  # debajo del logo
            except Exception:
                # Si falla, seguimos sin logo
                y_emisor_inicio = logo_y_top - 10
        else:
            y_emisor_inicio = logo_y_top - 10
    else:
        y_emisor_inicio = logo_y_top - 10

    # Bloque emisor debajo del logo
    y = y_emisor_inicio
    c.setFont("Helvetica-Bold", 12)
    if emisor.nombre:
        c.drawString(margen_x, y, emisor.nombre)
        y -= 15

    c.setFont("Helvetica", 10)

    # Dirección en varias líneas
    direccion_parts = []
    if getattr(emisor, "direccion", None):
        direccion_parts.append(emisor.direccion)
    localidad = " ".join(
        part for part in [
            getattr(emisor, "cp", None) or "",
            getattr(emisor, "poblacion", None) or "",
        ] if part
    ).strip()
    if localidad:
        direccion_parts.append(localidad)
    provincia_pais = " ".join(
        part for part in [
            getattr(emisor, "provincia", None) or "",
            getattr(emisor, "pais", None) or "",
        ] if part
    ).strip()
    if provincia_pais:
        direccion_parts.append(provincia_pais)

    for linea_dir in direccion_parts:
        for linea_wrap in textwrap.wrap(linea_dir, width=50):
            c.drawString(margen_x, y, linea_wrap)
            y -= 12

    if emisor.nif:
        c.drawString(margen_x, y, f"CIF: {emisor.nif}")
        y -= 12
    if emisor.telefono:
        c.drawString(margen_x, y, f"Tel: {emisor.telefono}")
        y -= 12
    if emisor.email:
        c.drawString(margen_x, y, f"Email: {emisor.email}")
        y -= 12

    y_emisor_fin = y  # para calcular dónde empezar la tabla


    # =============================
    # CABECERA DERECHA (FECHA + Nº FACTURA)
    # =============================
    c.setFont("Helvetica-Bold", 11)
    x_right = ancho - margen_x
    y_right = alto - 70  # algo por debajo del título

    c.drawRightString(x_right, y_right, f"Fecha: {factura.fecha.strftime('%d/%m/%Y')}")
    y_right -= 15
    c.drawRightString(x_right, y_right, f"Nº FACTURA: {factura.numero}")
    y_right -= 25

    # =============================
    # DATOS CLIENTE (DERECHA, alineado aprox. con emisor)
    # =============================
    cliente = factura.cliente

    y_cliente = y_emisor_inicio  # alineamos verticalmente con el bloque emisor
    x_cliente = ancho / 2 + 120   # mitad derecha

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_cliente, y_cliente, "Datos del cliente:")
    y_cliente -= 15

    c.setFont("Helvetica", 10)
    if getattr(cliente, "nombre", None):
        c.drawString(x_cliente, y_cliente, cliente.nombre)
        y_cliente -= 12
    if getattr(cliente, "nif", None):
        c.drawString(x_cliente, y_cliente, f"NIF: {cliente.nif}")
        y_cliente -= 12

    # Dirección cliente
    dir_cli_parts = []
    if cliente.direccion:
        dir_cli_parts.append(cliente.direccion)
    loc_cli = " ".join(
        part for part in [
            cliente.cp or "",
            cliente.poblacion or "",
        ] if part
    ).strip()
    if loc_cli:
        dir_cli_parts.append(loc_cli)
    prov_pais_cli = " ".join(
        part for part in [
            cliente.provincia or "",
            cliente.pais or "",
        ] if part
    ).strip()
    if prov_pais_cli:
        dir_cli_parts.append(prov_pais_cli)

    for linea_dir in dir_cli_parts:
        for linea_wrap in textwrap.wrap(linea_dir, width=40):
            c.drawString(x_cliente, y_cliente, linea_wrap)
            y_cliente -= 12

    y_cliente_fin = y_cliente

    # =============================
    # TABLA DE LÍNEAS
    # =============================
    # Punto de inicio de la tabla: un poco por debajo de lo más bajo entre emisor y cliente
    y = min(y_emisor_fin, y_cliente_fin) - 25
    c.setFont("Helvetica-Bold", 10)

    # Encabezados
    c.drawString(margen_x, y, "CANT.")
    c.drawString(margen_x + 60, y, "DESCRIPCIÓN")
    c.drawRightString(ancho - 120, y, "P. UNIT.")
    c.drawRightString(ancho - 30, y, "TOTAL")
    y -= 15

    c.setFont("Helvetica", 9)
    ancho_col_desc = (ancho - margen_x - 150) - (margen_x + 60)  # espacio aproximado para descripción

    for l in lineas:
        # Salto de página si hace falta
        if y < 120:
            c.showPage()
            ancho, alto = A4
            margen_x = 30
            y = alto - 80

            # Redibujar encabezados de tabla en nueva página
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margen_x, y, "CANT.")
            c.drawString(margen_x + 60, y, "DESCRIPCIÓN")
            c.drawRightString(ancho - 120, y, "P. UNIT.")
            c.drawRightString(ancho - 30, y, "TOTAL")
            y -= 15
            c.setFont("Helvetica", 9)

        desc = l.descripcion or ""
        desc_lines = simpleSplit(desc, "Helvetica", 9, ancho_col_desc)

        # Coordenadas base de la línea
        y_line_base = y

        # Descripción (puede ocupar varias líneas)
        for linea_desc in desc_lines:
            c.drawString(margen_x + 60, y, linea_desc)
            y -= 10

        # Cantidad, precio y total centrados verticalmente en el bloque ocupado
        bloque_altura = y_line_base - y
        y_centro = y_line_base - (bloque_altura / 2)

        c.drawCentredString(margen_x + 20, y_centro, f"{float(l.cantidad):.2f}")
        c.drawRightString(ancho - 120, y_centro, f"{float(l.precio_unitario):.2f} €")
        c.drawRightString(ancho - 30, y_centro, f"{float(l.total):.2f} €")

        y -= 10  # separación entre líneas

    # FIN DEL BUCLE DE LÍNEAS
    # ========================================================


    # =============================
    # TOTALES ABAJO DERECHA
    # =============================
    c.setFont("Helvetica-Bold", 11)
    x_totales = ancho - margen_x

    y_totales = 140  # bajar totales correctamente

    subtotal = float(factura.subtotal or 0)
    iva_total = float(factura.iva_total or 0)
    total = float(factura.total or 0)
    iva_tipo = float(factura.iva_global or 0)

    c.drawRightString(x_totales, y_totales, f"Subtotal: {subtotal:.2f} €")
    y_totales -= 16

    c.drawRightString(x_totales, y_totales, f"IVA ({iva_tipo:.2f}%): {iva_total:.2f} €")
    y_totales -= 16

    c.drawRightString(x_totales, y_totales, f"TOTAL FACTURA: {total:.2f} €")
    y_totales -= 25

    # =============================
    # QR VERI*FACTU (encima de totales)
    # =============================
    qr_y = None  # ← CLAVE

    if config and factura.verifactu_hash:
        try:
            url_qr = construir_url_qr(
                factura=factura,
                emisor=emisor,
                config=config,
                entorno="PRUEBAS" if config.verifactu_modo == "TEST" else "PRODUCCION",
                es_verifactu=True,
            )

            qr_size_mm = 35
            qr_size = qr_size_mm * mm

            qr_x = ancho - margen_x - qr_size
            qr_y = y_totales + 120

            dibujar_qr(
                c,
                url_qr,
                x=qr_x,
                y=qr_y,
                size_mm=qr_size_mm,
            )

            c.setFont("Helvetica", 8)
            c.drawRightString(
                ancho - margen_x,
                qr_y - 10,
                "Factura verificable en la sede electrónica de la AEAT",
            )

        except Exception as e:
            print("ERROR QR VERIFACTU:", e)
            qr_y = None  # seguridad extra


    # =============================
    # HASH VERI*FACTU IMPRESO (COMPLETO, EN 2 LÍNEAS)
    # =============================
    if factura.verifactu_hash and qr_y is not None:
        h = factura.verifactu_hash.strip()
        c.setFont("Helvetica", 7)

        # 64 hex -> 2 líneas de 32 + 32
        h1, h2 = h[:32], h[32:]

        c.drawRightString(
            ancho - margen_x,
            qr_y - 44,
            "Sistema de facturación verificable (Veri*Factu)",
        )
        c.drawRightString(ancho - margen_x, qr_y - 32, f"Hash: {h1}")
        c.drawRightString(ancho - margen_x, qr_y - 22, h2)

    # =============================
    # MENSAJE IVA ENCIMA DE TOTALES # Mensaje IVA informativo (NO forma parte del hash Veri*Factu)
    # =============================
    mensaje_iva = (factura.mensaje_iva or "").strip()

    y_iva_msg = 80  # bajar mensaje IVA

    if incluir_mensaje_iva and mensaje_iva:
        c.setFont("Helvetica-Oblique", 10)
        for linea in textwrap.wrap(mensaje_iva, 90):
            c.drawString(margen_x, y_iva_msg, linea)
            y_iva_msg -= 12

    # =============================
    # TEXTOS LEGALES ABAJO IZQUIERDA
    # =============================
    y_legal = 50
    c.setFont("Helvetica", 9)

    # Texto pie del emisor
    if emisor.texto_pie:
        y_legal -= 10
        for linea in textwrap.wrap(emisor.texto_pie, 90):
            c.drawString(margen_x, y_legal, linea)
            y_legal -= 12


    c.save()

    # ============================================
    # RETURN
    # ============================================
    if en_render:
        buffer.seek(0)
        return buffer, None

    rel = ruta_pdf.replace(str(base_dir), "").replace("\\", "/")
    ruta_url = f"/pdf{rel}"
    return ruta_pdf, ruta_url

def dibujar_qr(c, url: str, x: float, y: float, size_mm: float = 35):
    """
    Dibuja un QR conforme a ISO/IEC 18004.
    Tamaño recomendado AEAT: 30–40 mm.
    """
    qr = QrCodeWidget(url)
    bounds = qr.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]

    size = size_mm * mm
    d = Drawing(
        size,
        size,
        transform=[size / w, 0, 0, size / h, 0, 0],
    )
    d.add(qr)
    d.drawOn(c, x, y)
