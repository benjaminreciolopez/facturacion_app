from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import extract, func
from datetime import date, timedelta, datetime

from app.db.session import get_session
from app.models.factura import Factura
from app.models.cliente import Cliente
from app.models.emisor import Emisor
from app.models.iva import IVA
from app.models.configuracion_sistema import ConfiguracionSistema
from app.core.templates import templates
from sqlalchemy import or_

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
    cliente_id: str | None = Query(None),
    estado: str | None = Query(None),
    year: str | None = Query(None),
):
    hoy = date.today()

    # =========================
    # NORMALIZAR FILTROS
    # =========================
    cliente_id = int(cliente_id) if cliente_id and cliente_id.isdigit() else None
    estado = estado or None
    year = int(year) if year and year.isdigit() else hoy.year

    year_anterior = year - 1

    # =========================
    # FILTROS BASE
    # =========================
    if estado:
        # Si el usuario filtra manualmente → respetamos el filtro
        filtros = [
            Factura.estado == estado,
            extract("year", Factura.fecha) == year
        ]
    else:
        # Modo dashboard → actividad emitida

        filtros = [
            extract("year", Factura.fecha) == year,
            or_(
                Factura.estado == "VALIDADA",
                Factura.estado == "ANULADA"
            ),
            Factura.rectificativa == False   # o 0 según tu modelo
        ]

    if cliente_id:
        filtros.append(Factura.cliente_id == cliente_id)

    # =========================
    # FACTURACIÓN MENSUAL (solo VALIDADAS)
    # =========================
    mes_expr = extract("month", Factura.fecha)

    rows = session.exec(
        select(
            mes_expr,
            func.sum(Factura.total)
        )
        .where(*filtros)
        .group_by(mes_expr)
        .order_by(mes_expr)
    ).all()

    meses = [int(r[0]) for r in rows]
    totales = [float(r[1] or 0) for r in rows]

    # =========================
    # KPIs (SIEMPRE VALIDADAS)
    # =========================
    filtros_kpi = [
        extract("year", Factura.fecha) == year,
        or_(
            Factura.estado == "VALIDADA",
            Factura.estado == "ANULADA"
        ),
        Factura.rectificativa == False
    ]

    if cliente_id:
        filtros_kpi.append(Factura.cliente_id == cliente_id)

    total_anual = session.exec(
        select(func.coalesce(func.sum(Factura.total), 0))
        .where(*filtros)
    ).one()

    facturas_total = session.exec(
        select(func.count(Factura.id))
        .where(*filtros_kpi)
    ).one()


    # =========================
    # COMPARATIVA ANUAL
    # =========================
    anterior = session.exec(
        select(func.coalesce(func.sum(Factura.total), 0))
        .where(
            extract("year", Factura.fecha) == year_anterior,
            or_(
                Factura.estado == "VALIDADA",
                Factura.estado == "ANULADA"
            ),
            Factura.rectificativa == False
        )
    ).one()


    # =========================
    # ALERTAS AVANZADAS DASHBOARD
    # =========================
    alertas: list[dict] = []
    emisor = session.get(Emisor, 1)


    hoy = date.today()
    year_actual = hoy.year
    year_anterior = year_actual - 1

    # -------------------------------------------------
    # 1️⃣ ALERTAS CON ACCIÓN (CONFIGURACIÓN)
    # -------------------------------------------------
    def alerta(tipo, mensaje, accion=None):
        data = {"tipo": tipo, "mensaje": mensaje}
        if accion:
            data["accion"] = accion
        return data


    # -------------------------------------------------
    # 2️⃣ CAÍDA DE FACTURACIÓN VS AÑO ANTERIOR
    # -------------------------------------------------
    total_actual = session.exec(
        select(func.coalesce(func.sum(Factura.total), 0))
        .where(Factura.estado == "VALIDADA")
        .where(extract("year", Factura.fecha) == year_actual)
    ).one()

    total_anterior = session.exec(
        select(func.coalesce(func.sum(Factura.total), 0))
        .where(Factura.estado == "VALIDADA")
        .where(extract("year", Factura.fecha) == year_anterior)
    ).one()

    variacion = None

    if total_anterior > 0:
        variacion = ((total_actual - total_anterior) / total_anterior) * 100

    if variacion is not None:
        if variacion <= -40:
            alertas.append(alerta(
                "error",
                f"Caída crítica de facturación: {abs(variacion):.1f}% respecto al año anterior."
            ))
        elif variacion <= -20:
            alertas.append(alerta(
                "warning",
                f"La facturación ha caído un {abs(variacion):.1f}% respecto al año anterior."
            ))


    # -------------------------------------------------
    # 3️⃣ IVA NO CONFIGURADO
    # -------------------------------------------------
    ivas_activos = session.exec(
        select(func.count(IVA.id))
        .where(IVA.activo == True)
    ).one()

    if ivas_activos == 0:
        alertas.append(alerta(
            "warning",
            "No hay tipos de IVA configurados en el sistema.",
            accion={
                "texto": "Configurar IVA",
                "url": "/configuracion/iva"
            }
        ))


    # -------------------------------------------------
    # 4️⃣ FACTURAS EN BORRADOR ANTIGUAS
    # -------------------------------------------------
    limite_borrador = hoy - timedelta(days=30)

    borradores_antiguos = session.exec(
        select(func.count(Factura.id))
        .where(Factura.estado == "BORRADOR")
        .where(Factura.fecha < limite_borrador)
    ).one()

    if borradores_antiguos > 0:
        alertas.append(alerta(
            "info",
            (
                f"Hay {borradores_antiguos} factura(s) en borrador "
                f"con más de 30 días."
            ),
            accion={
                "texto": "Revisar borradores",
                "url": "/facturas?estado=BORRADOR"
            }
        ))


    # -------------------------------------------------
    # 5️⃣ FACTURAS VALIDABLES SIN NUMERAR (CONTROL FISCAL)
    # -------------------------------------------------
    pendientes_validar = session.exec(
        select(func.count(Factura.id))
        .where(Factura.estado == "BORRADOR")
    ).one()

    if pendientes_validar > 0:
        alertas.append(alerta(
            "info",
            f"Tienes {pendientes_validar} factura(s) pendientes de validar.",
            accion={
                "texto": "Ir a facturas",
                "url": "/facturas"
            }
        ))
    # -------------------------------------------------
    # CERTIFICADO DIGITAL
    # -------------------------------------------------
    if emisor and emisor.certificado_path:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from pathlib import Path
        from datetime import datetime, timezone

        try:
            path = Path(emisor.certificado_path).resolve()

            if not path.exists():
                raise Exception("Certificado no encontrado en disco")

            with open(path, "rb") as f:
                pfx_data = f.read()

            _, cert, _ = pkcs12.load_key_and_certificates(
                pfx_data,
                emisor.certificado_password.encode()
                if emisor.certificado_password else None
            )

            # Compatibilidad con versiones antiguas y nuevas
            fecha_exp = getattr(cert, "not_valid_after_utc", cert.not_valid_after)

            now = datetime.now(timezone.utc)
            dias_restantes = (fecha_exp - now).days

            if dias_restantes < 0:
                alertas.append({
                    "tipo": "error",
                    "mensaje": (
                        "El certificado digital está CADUCADO. "
                        "No podrás firmar ni validar facturas."
                    )
                })

            elif dias_restantes <= 30:
                alertas.append({
                    "tipo": "warning",
                    "mensaje": (
                        f"El certificado digital caduca en {dias_restantes} días. "
                        "Renovación urgente recomendada."
                    )
                })

            elif dias_restantes <= 60:
                alertas.append({
                    "tipo": "info",
                    "mensaje": (
                        f"El certificado digital caduca en {dias_restantes} días."
                    )
                })

        except Exception as e:
            alertas.append({
                "tipo": "error",
                "mensaje": (
                    "No se pudo leer el certificado digital configurado. "
                    "Revisa el archivo y la contraseña."
                )
            })

    else:
        alertas.append({
            "tipo": "warning",
            "mensaje": (
                "No hay certificado digital configurado. "
                "No podrás firmar facturas."
            )
        })

    # -------------------------------------------------
    # NUMERACIÓN DE FACTURAS
    # -------------------------------------------------
    if emisor and emisor.numeracion_bloqueada:
        alertas.append({
            "tipo": "info",
            "mensaje": (
                "La numeración de facturas está bloqueada para este ejercicio."
            )
        })

    # -------------------------------------------------
    # RUTA DE PDFs
    # -------------------------------------------------
    if not emisor or not emisor.ruta_pdf:
        alertas.append({
            "tipo": "warning",
            "mensaje": (
                "No hay una ruta configurada para guardar los PDF de las facturas."
            )
        })

    # -------------------------------------------------
    # VERI*FACTU CONFIGURACIÓN
    # -------------------------------------------------

    config = session.get(ConfiguracionSistema, 1)

    if config.verifactu_modo in ("TEST", "PRODUCCION") and not config.cert_aeat_path:
        alertas.append({
            "tipo": "error",
            "mensaje": "Veri*Factu activo pero no hay certificado AEAT configurado.",
            "accion": {
                "texto": "Configurar sistema",
                "url": "/configuracion/sistema"
            }
        })

    # -------------------------------------------------
    # ACTIVIDAD DE FACTURACIÓN (AÑO ACTUAL)
    # -------------------------------------------------
    year_actual = date.today().year

    facturas_ano = session.exec(
        select(func.count(Factura.id))
        .where(Factura.estado == "VALIDADA")
        .where(extract("year", Factura.fecha) == year_actual)
    ).one() or 0

    if facturas_ano == 0:
        alertas.append({
            "tipo": "info",
            "mensaje": (
                "Aún no hay facturas validadas en el año en curso."
            )
        })

    # -------------------------------------------------
    # FACTURACIÓN ÚLTIMO MES
    # -------------------------------------------------
    hoy = date.today()
    mes_actual = hoy.month

    facturas_mes = session.exec(
        select(func.count(Factura.id))
        .where(Factura.estado == "VALIDADA")
        .where(extract("year", Factura.fecha) == year_actual)
        .where(extract("month", Factura.fecha) == mes_actual)
    ).one() or 0

    if facturas_mes == 0:
        alertas.append({
            "tipo": "info",
            "mensaje": (
                "No se ha emitido ninguna factura validada en el mes actual."
            )
        })

    # -------------------------------------------------
    # CLIENTES
    # -------------------------------------------------
    clientes_total = session.exec(
        select(func.count(Cliente.id))
    ).one() or 0

    if clientes_total == 0:
        alertas.append({
            "tipo": "warning",
            "mensaje": (
                "No hay clientes registrados. "
                "No podrás emitir facturas."
            )
        })

    # =========================
    # DATOS PARA FILTROS
    # =========================
    clientes = session.exec(
        select(Cliente).order_by(Cliente.nombre)
    ).all()

    estados_disponibles = ["VALIDADA", "BORRADOR", "ANULADA"]

    # =========================
    # RENDER
    # =========================
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_anual": total_anual,
            "facturas_total": facturas_total,
            "meses": meses,
            "totales": totales,
            "comparativa": {
                "actual": total_anual,
                "anterior": anterior
            },
            "alertas": alertas,
            "clientes": clientes,
            "cliente_id": cliente_id,
            "estado": estado,
            "year": year,
            "estados_disponibles": estados_disponibles,
            "sin_datos": len(meses) == 0
        }
    )
