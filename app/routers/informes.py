from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from sqlmodel import Session, select
from datetime import date
import calendar
from app.core.templates import templates
import os
import csv
from io import StringIO, BytesIO
from openpyxl import Workbook

from app.db.session import get_session
from app.models.factura import Factura
from app.models.cliente import Cliente
from app.models.emisor import Emisor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from tempfile import NamedTemporaryFile
from sqlalchemy import extract, func, case

router = APIRouter(prefix="/informes", tags=["Informes"])



@router.get("", response_class=HTMLResponse)
def informes_home(
    request: Request,
    session: Session = Depends(get_session),
):
    return templates.TemplateResponse(
        "informes/index.html",
        {
            "request": request,
            "current_year": date.today().year,

        },
    )


from fastapi import Request
from pathlib import Path
from app.utils.session_empresa import get_empresa_id


@router.get("/pdf/{year}/{trimestre}/{filename}")
def servir_pdf(
    request: Request,
    year: int,
    trimestre: str,
    filename: str,
    session: Session = Depends(get_session),
):
    # ============================
    # Multiempresa
    # ============================
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor or not emisor.ruta_pdf:
        raise HTTPException(404, "No hay ruta de PDFs configurada para esta empresa.")

    # ============================
    # Render NO sirve PDFs
    # ============================
    if os.getenv("RENDER"):
        raise HTTPException(
            400,
            "En este entorno los PDF no se almacenan en servidor. Descárgalo o solicítalo de nuevo."
        )

    # ============================
    # Validar trimestre formato
    # ============================
    trimestre = trimestre.upper()
    if trimestre not in {"T1", "T2", "T3", "T4"}:
        raise HTTPException(400, "Trimestre no válido")

    # ============================
    # Seguridad filename
    # ============================
    filename = os.path.basename(filename)

    base = Path(emisor.ruta_pdf)
    ruta = base / str(year) / trimestre / filename

    if not ruta.exists():
        raise HTTPException(
            404,
            f"El PDF no existe en el servidor ({ruta}).",
        )

    return FileResponse(
        ruta,
        media_type="application/pdf",
        filename=filename,
    )


# ============================================================
# EXPORTAR CLIENTES CSV
# ============================================================
@router.get("/export/clientes.csv")
def export_clientes_csv(
    session: Session = Depends(get_session),
):
    clientes = session.exec(
        select(Cliente).order_by(Cliente.nombre)
    ).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Nombre",
        "NIF",
        "Teléfono",
        "Email",
        "Población",
        "Provincia",
        "CP",
        "País",
        "Fecha Alta",
    ])

    for c in clientes:
        writer.writerow([
            c.nombre,
            c.nif,
            c.telefono,
            c.email,
            c.poblacion,
            c.provincia,
            c.cp,
            c.pais,
            c.fecha_alta,
        ])

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=clientes.csv"
        },
    )


# ============================================================
# EXPORTAR CLIENTES EXCEL
# ============================================================
@router.get("/export/clientes.xlsx")
def export_clientes_excel(
    session: Session = Depends(get_session),
):
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"

    ws.append([
        "Nombre",
        "NIF",
        "Teléfono",
        "Email",
        "Población",
        "Provincia",
        "CP",
        "País",
        "Fecha Alta",
    ])

    clientes = session.exec(
        select(Cliente).order_by(Cliente.nombre)
    ).all()

    for c in clientes:
        ws.append([
            c.nombre,
            c.nif,
            c.telefono,
            c.email,
            c.poblacion,
            c.provincia,
            c.cp,
            c.pais,
            str(c.fecha_alta),
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=clientes.xlsx"
        },
    )


# ============================================================
# EXPORTAR FACTURAS CSV
# ============================================================
@router.get("/export/facturas.csv")
def export_facturas_csv(
    year: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    session: Session = Depends(get_session),
):
    query = select(Factura)

    if year:
        query = query.where(
            Factura.fecha >= date(year, 1, 1),
            Factura.fecha <= date(year, 12, 31),
        )

    if fecha_desde:
        query = query.where(Factura.fecha >= fecha_desde)

    if fecha_hasta:
        query = query.where(Factura.fecha <= fecha_hasta)

    facturas = session.exec(
        query.order_by(Factura.fecha)
    ).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Número",
        "Cliente",
        "Fecha",
        "Subtotal",
        "IVA",
        "Total",
        "Estado",
    ])

    for f in facturas:
        writer.writerow([
            f.numero,
            f.cliente.nombre if f.cliente else "-",
            f.fecha,
            f.subtotal,
            f.iva_total,
            f.total,
            f.estado,
        ])

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=facturas.csv"
        },
    )

@router.get("/export/clientes.pdf")
def export_clientes_pdf(
    session: Session = Depends(get_session),
):
    clientes = session.exec(
        select(Cliente).order_by(Cliente.nombre)
    ).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    # Cabecera
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, y, "Listado de clientes")
    y -= 1 * cm

    pdf.setFont("Helvetica", 9)
    pdf.drawString(2 * cm, y, f"Fecha: {date.today().strftime('%d/%m/%Y')}")
    y -= 1 * cm

    # Tabla
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(2 * cm, y, "Nombre")
    pdf.drawString(8 * cm, y, "NIF")
    pdf.drawString(12 * cm, y, "Email")
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 9)

    for c in clientes:
        if y < 2 * cm:
            pdf.showPage()
            y = height - 2 * cm
            pdf.setFont("Helvetica", 9)

        pdf.drawString(2 * cm, y, c.nombre or "")
        pdf.drawString(8 * cm, y, c.nif or "")
        pdf.drawString(12 * cm, y, c.email or "")
        y -= 0.4 * cm

    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=clientes.pdf"
        },
    )

@router.get("/export/facturas.pdf")
def export_facturas_pdf(
    year: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    session: Session = Depends(get_session),
):
    query = select(Factura).order_by(Factura.fecha)

    if year:
        query = query.where(
            Factura.fecha >= date(year, 1, 1),
            Factura.fecha <= date(year, 12, 31),
        )

    if fecha_desde:
        query = query.where(Factura.fecha >= fecha_desde)

    if fecha_hasta:
        query = query.where(Factura.fecha <= fecha_hasta)

    facturas = session.exec(query).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    # Cabecera
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, y, "Listado de facturas")
    y -= 1 * cm

    pdf.setFont("Helvetica", 9)
    pdf.drawString(2 * cm, y, f"Fecha: {date.today().strftime('%d/%m/%Y')}")
    y -= 1 * cm

    # Encabezados tabla
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(2 * cm, y, "Número")
    pdf.drawString(5 * cm, y, "Cliente")
    pdf.drawString(10 * cm, y, "Fecha")
    pdf.drawString(13 * cm, y, "Total")
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 9)

    total_general = 0

    for f in facturas:
        if y < 2 * cm:
            pdf.showPage()
            y = height - 2 * cm
            pdf.setFont("Helvetica", 9)

        pdf.drawString(2 * cm, y, f.numero or "")
        pdf.drawString(5 * cm, y, f.cliente.nombre if f.cliente else "-")
        pdf.drawString(10 * cm, y, f.fecha.strftime("%d/%m/%Y"))
        pdf.drawRightString(18 * cm, y, f"{f.total:.2f} €")

        total_general += f.total or 0
        y -= 0.4 * cm

    # Total
    y -= 0.5 * cm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(
        18 * cm,
        y,
        f"TOTAL: {total_general:.2f} €"
    )

    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=facturas.pdf"
        },
    )

@router.get("/iva/trimestral", response_class=HTMLResponse)
def iva_trimestral_view(
    request: Request,
    year: int,
    trimestre: int,
    session: Session = Depends(get_session),
):
    if trimestre not in (1, 2, 3, 4):
        raise HTTPException(400, "Trimestre no válido")

    meses = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12),
    }[trimestre]

    datos = session.exec(
        select(
            Factura.iva_global,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
            func.sum(
                case(
                    (Factura.estado == "ANULADA", 1),
                    else_=0
                )
            ).label("anuladas")
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
        .where(extract("year", Factura.fecha) == year)
        .where(extract("month", Factura.fecha) >= meses[0])
        .where(extract("month", Factura.fecha) <= meses[1])
        .group_by(Factura.iva_global)
        .order_by(Factura.iva_global)
    ).all()

    resumen = [
        {
            "iva": r[0],
            "facturas": int(r[1]),
            "base": float(r[2] or 0),
            "cuota": float(r[3] or 0),
            "total": float(r[4] or 0),
            "anuladas": int(r[5] or 0),
        }
        for r in datos
    ]

    total_base = sum(r["base"] for r in resumen)
    total_iva = sum(r["cuota"] for r in resumen)
    total_total = sum(r["total"] for r in resumen)
    total_facturas = sum(r["facturas"] for r in resumen)
    total_anuladas = sum(r["anuladas"] for r in resumen)

    return templates.TemplateResponse(
        "informes/iva_trimestral.html",
        {
            "request": request,
            "year": year,
            "current_year": date.today().year,
            "trimestre": trimestre,
            "resumen": resumen,
            "total_base": total_base,
            "total_iva": total_iva,
            "total_total": total_total,
            "total_facturas": total_facturas,
            "total_anuladas": total_anuladas,
        },
    )

@router.get("/iva/trimestral.pdf")
def iva_trimestral_pdf(
    year: int,
    trimestre: int,
    session: Session = Depends(get_session),
):
    if trimestre not in (1, 2, 3, 4):
        raise HTTPException(400, "Trimestre no válido")

    meses = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12),
    }[trimestre]

    rows = session.exec(
        select(
            Factura.iva_global,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
            func.sum(
                case(
                    (Factura.estado == "ANULADA", 1),
                    else_=0
                )
            ).label("anuladas")
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
        .where(extract("year", Factura.fecha) == year)
        .where(extract("month", Factura.fecha) >= meses[0])
        .where(extract("month", Factura.fecha) <= meses[1])
        .group_by(Factura.iva_global)
        .order_by(Factura.iva_global)
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Informe IVA Trimestre {trimestre} / {year}")

    # Encabezados
    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "IVA %")
    c.drawRightString(140, y, "Facturas")
    c.drawRightString(220, y, "Anuladas")
    c.drawRightString(340, y, "Base (€)")
    c.drawRightString(430, y, "IVA (€)")
    c.drawRightString(520, y, "Total (€)")

    c.setFont("Helvetica", 10)

    total_facturas = 0
    total_anuladas = 0
    total_base = 0
    total_iva = 0
    total_total = 0

    for iva, n, base, cuota, total, anuladas in rows:
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)

        base = base or 0
        cuota = cuota or 0
        total = total or 0

        c.drawString(40, y, f"{iva:.2f}%")
        c.drawRightString(140, y, str(n))
        c.drawRightString(220, y, str(anuladas or 0))
        c.drawRightString(340, y, f"{base:.2f}")
        c.drawRightString(430, y, f"{cuota:.2f}")
        c.drawRightString(520, y, f"{total:.2f}")

        total_facturas += n or 0
        total_anuladas += anuladas or 0
        total_base += base
        total_iva += cuota
        total_total += total

    # Totales
    y -= 28
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "TOTALES")
    c.drawRightString(140, y, str(total_facturas))
    c.drawRightString(220, y, str(total_anuladas))
    c.drawRightString(340, y, f"{total_base:.2f}")
    c.drawRightString(430, y, f"{total_iva:.2f}")
    c.drawRightString(520, y, f"{total_total:.2f}")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename=f"IVA_T{trimestre}_{year}.pdf",
    )


@router.get("/facturacion/anual", response_class=HTMLResponse)
def facturacion_anual_view(
    request: Request,
    year: int,
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(
            extract("month", Factura.fecha).label("mes"),
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
        .where(extract("year", Factura.fecha) == year)
        .group_by("mes")
        .order_by("mes")
    ).all()

    meses = []
    total_facturas = total_base = total_iva = total = 0

    for mes, n, base, iva, tot in rows:
        meses.append({
            "mes": int(mes),
            "facturas": n,
            "base": float(base or 0),
            "iva": float(iva or 0),
            "total": float(tot or 0),
        })
        total_facturas += n
        total_base += base or 0
        total_iva += iva or 0
        total += tot or 0

    return templates.TemplateResponse(
        "informes/facturacion_anual.html",
        {
            "request": request,
            "year": year,
            "current_year": date.today().year,
            "meses": meses,
            "total_facturas": total_facturas,
            "total_base": total_base,
            "total_iva": total_iva,
            "total": total,
        },
    )

@router.get("/facturacion/anual.pdf")
def facturacion_anual_pdf(
    year: int,
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(
            extract("month", Factura.fecha).label("mes"),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
        .where(extract("year", Factura.fecha) == year)
        .group_by("mes")
        .order_by("mes")
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Facturación Anual {year}")

    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Mes")
    c.drawString(120, y, "Base")
    c.drawString(220, y, "IVA")
    c.drawString(320, y, "Total")

    c.setFont("Helvetica", 10)
    total_base = total_iva = total = 0

    for mes, base, iva, tot in rows:
        y -= 18
        c.drawString(50, y, f"{int(mes):02d}")
        c.drawRightString(200, y, f"{base or 0:.2f} €")
        c.drawRightString(300, y, f"{iva or 0:.2f} €")
        c.drawRightString(400, y, f"{tot or 0:.2f} €")

        total_base += base or 0
        total_iva += iva or 0
        total += tot or 0

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "TOTAL")
    c.drawRightString(200, y, f"{total_base:.2f} €")
    c.drawRightString(300, y, f"{total_iva:.2f} €")
    c.drawRightString(400, y, f"{total:.2f} €")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename=f"Facturacion_{year}.pdf",
    )

@router.get("/clientes/ranking", response_class=HTMLResponse)
def ranking_clientes_view(
    request: Request,
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Cliente.id,
            Cliente.nombre,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .join(Factura, Factura.cliente_id == Cliente.id)
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Cliente.id)
             .order_by(func.sum(Factura.total).desc())
    ).all()

    clientes = []
    total_global = 0

    for _, nombre, n, base, iva, total in rows:
        clientes.append({
            "nombre": nombre,
            "facturas": n,
            "base": float(base or 0),
            "iva": float(iva or 0),
            "total": float(total or 0),
        })
        total_global += total or 0

    return templates.TemplateResponse(
        "informes/ranking_clientes.html",
        {
            "request": request,
            "clientes": clientes,
            "year": year,
            "current_year": date.today().year,
            "total_global": total_global,
        },
    )

@router.get("/clientes/ranking.pdf")
def ranking_clientes_pdf(
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Cliente.nombre,
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .join(Factura, Factura.cliente_id == Cliente.id)
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Cliente.id)
             .order_by(func.sum(Factura.total).desc())
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    titulo = "Ranking de Clientes"
    if year:
        titulo += f" ({year})"
    c.drawString(50, y, titulo)

    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Cliente")
    c.drawString(280, y, "Base")
    c.drawString(360, y, "IVA")
    c.drawString(440, y, "Total")

    c.setFont("Helvetica", 10)
    total_global = 0

    for nombre, base, iva, total in rows:
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 50

        c.drawString(50, y, nombre[:40])
        c.drawRightString(340, y, f"{base or 0:.2f} €")
        c.drawRightString(420, y, f"{iva or 0:.2f} €")
        c.drawRightString(500, y, f"{total or 0:.2f} €")

        total_global += total or 0

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "TOTAL FACTURADO")
    c.drawRightString(500, y, f"{total_global:.2f} €")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename="Ranking_Clientes.pdf",
    )


@router.get("/clientes-ranking", response_class=HTMLResponse)
def informe_ranking_clientes(
    request: Request,
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Cliente.id,
            Cliente.nombre,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .join(Factura, Factura.cliente_id == Cliente.id)
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Cliente.id)
             .order_by(func.sum(Factura.total).desc())
    ).all()

    ranking = []
    total_facturado = 0

    for cid, nombre, num, base, iva, total in rows:
        ranking.append({
            "cliente": nombre,
            "num_facturas": num,
            "base": float(base or 0),
            "iva": float(iva or 0),
            "total": float(total or 0),
        })
        total_facturado += total or 0

    return templates.TemplateResponse(
        "informes/clientes_ranking.html",
        {
            "request": request,
            "ranking": ranking,
            "year": year,
            "current_year": date.today().year,
            "total_facturado": total_facturado,
        },
    )

@router.get("/clientes-ranking.pdf")
def informe_ranking_clientes_pdf(
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Cliente.nombre,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .join(Factura, Factura.cliente_id == Cliente.id)
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Cliente.nombre)
             .order_by(func.sum(Factura.total).desc())
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    titulo = "Ranking de clientes"
    if year:
        titulo += f" ({year})"
    c.drawString(50, y, titulo)

    y -= 40
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Cliente")
    c.drawRightString(270, y, "Facturas")
    c.drawRightString(350, y, "Base")
    c.drawRightString(430, y, "IVA")
    c.drawRightString(520, y, "Total")

    c.setFont("Helvetica", 9)

    total_fact = 0

    for nombre, num, base, iva, total in rows:
        y -= 16
        if y < 60:
            c.showPage()
            y = height - 50

        c.drawString(50, y, nombre[:30])
        c.drawRightString(270, y, str(num))
        c.drawRightString(350, y, f"{base or 0:.2f} €")
        c.drawRightString(430, y, f"{iva or 0:.2f} €")
        c.drawRightString(520, y, f"{total or 0:.2f} €")

        total_fact += total or 0

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "TOTAL FACTURADO")
    c.drawRightString(520, y, f"{total_fact:.2f} €")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename="Ranking_clientes.pdf",
    )

@router.get("/iva", response_class=HTMLResponse)
def informe_iva_view(
    request: Request,
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Factura.iva_global,
            func.count(Factura.id),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
            func.sum(
                case(
                    (Factura.estado == "ANULADA", 1),
                    else_=0
                )
            ).label("anuladas")
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Factura.iva_global)
             .order_by(Factura.iva_global)
    ).all()

    ivas = []
    total_base = total_iva = total_fact = 0

    for iva, n, base, cuota, total, anuladas in rows:
        ivas.append({
            "iva": iva,
            "facturas": int(n),
            "anuladas": int(anuladas or 0),
            "base": float(base or 0),
            "cuota": float(cuota or 0),
            "total": float(total or 0),
        })
        total_base += base or 0
        total_iva += cuota or 0
        total_fact += total or 0

    return templates.TemplateResponse(
        "informes/iva.html",
        {
            "request": request,
            "year": year,
            "current_year": date.today().year,
            "ivas": ivas,
            "total_base": total_base,
            "total_iva": total_iva,
            "total_fact": total_fact,
        },
    )

@router.get("/iva.pdf")
def informe_iva_pdf(
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            Factura.iva_global,
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(Factura.iva_global)
             .order_by(Factura.iva_global)
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    titulo = "Facturación por Tipo de IVA"
    if year:
        titulo += f" ({year})"
    c.drawString(50, y, titulo)

    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "IVA %")
    c.drawString(150, y, "Base")
    c.drawString(270, y, "Cuota IVA")
    c.drawString(410, y, "Total")

    c.setFont("Helvetica", 10)

    total_base = total_iva = total_fact = 0

    for iva, base, cuota, total in rows:
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 50

        c.drawString(50, y, f"{iva:.2f} %")
        c.drawRightString(230, y, f"{base or 0:.2f} €")
        c.drawRightString(360, y, f"{cuota or 0:.2f} €")
        c.drawRightString(500, y, f"{total or 0:.2f} €")

        total_base += base or 0
        total_iva += cuota or 0
        total_fact += total or 0

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "TOTALES")
    c.drawRightString(230, y, f"{total_base:.2f} €")
    c.drawRightString(360, y, f"{total_iva:.2f} €")
    c.drawRightString(500, y, f"{total_fact:.2f} €")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename="Facturacion_por_IVA.pdf",
    )

@router.get("/mensual", response_class=HTMLResponse)
def informe_facturacion_mensual(
    request: Request,
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            extract("year", Factura.fecha).label("year"),
            extract("month", Factura.fecha).label("month"),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by("year", "month")
             .order_by("year", "month")
    ).all()

    meses = []
    total_base = total_iva = total_fact = 0

    for y, m, base, iva, total in rows:
        meses.append({
            "year": int(y),
            "month": int(m),
            "mes_nombre": calendar.month_name[int(m)],
            "base": float(base or 0),
            "iva": float(iva or 0),
            "total": float(total or 0),
        })
        total_base += base or 0
        total_iva += iva or 0
        total_fact += total or 0

    return templates.TemplateResponse(
        "informes/mensual.html",
        {
            "request": request,
            "year": year,
            "current_year": date.today().year,
            "meses": meses,
            "total_base": total_base,
            "total_iva": total_iva,
            "total_fact": total_fact,
        },
    )

@router.get("/mensual.pdf")
def informe_facturacion_mensual_pdf(
    year: int | None = None,
    session: Session = Depends(get_session),
):
    query = (
        select(
            extract("year", Factura.fecha),
            extract("month", Factura.fecha),
            func.sum(Factura.subtotal),
            func.sum(Factura.iva_total),
            func.sum(Factura.total),
        )
        .where(Factura.estado.in_(("VALIDADA", "ANULADA")))
    )

    if year:
        query = query.where(
            extract("year", Factura.fecha) == year
        )

    rows = session.exec(
        query.group_by(
            extract("year", Factura.fecha),
            extract("month", Factura.fecha),
        ).order_by(
            extract("year", Factura.fecha),
            extract("month", Factura.fecha),
        )
    ).all()

    tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    titulo = "Facturación mensual"
    if year:
        titulo += f" ({year})"
    c.drawString(50, y, titulo)

    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Mes")
    c.drawString(150, y, "Base")
    c.drawString(270, y, "IVA")
    c.drawString(390, y, "Total")

    c.setFont("Helvetica", 10)

    total_base = total_iva = total_fact = 0

    for y_, m_, base, iva, total in rows:
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 50

        mes_nombre = calendar.month_name[int(m_)]
        c.drawString(50, y, f"{mes_nombre} {int(y_)}")
        c.drawRightString(230, y, f"{base or 0:.2f} €")
        c.drawRightString(350, y, f"{iva or 0:.2f} €")
        c.drawRightString(500, y, f"{total or 0:.2f} €")

        total_base += base or 0
        total_iva += iva or 0
        total_fact += total or 0

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "TOTALES")
    c.drawRightString(230, y, f"{total_base:.2f} €")
    c.drawRightString(350, y, f"{total_iva:.2f} €")
    c.drawRightString(500, y, f"{total_fact:.2f} €")

    c.showPage()
    c.save()

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename="Facturacion_mensual.pdf",
    )
