from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query, Body, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, delete
from datetime import date
import os
import json
import re
from app.models.configuracion_sistema import ConfiguracionSistema
from app.db.session import get_session
from app.core.templates import templates
from app.models.linea_factura import LineaFactura
from app.models.cliente import Cliente
from app.models.emisor import Emisor
from app.models.iva import IVA
from app.models.envios_email import EnviosEmail, registrar_envio_email
from app.models.factura import Factura
from app.services.facturas_pdf import generar_factura_pdf
from app.services.control_verifactu import verificar_verifactu
from app.services.control_sistema import validar_fecha_factura, bloquear_edicion_factura, bloquear_borrado_factura
from app.services.facturas_service import generar_numero_factura, bloquear_numeracion, recalcular_totales  
from app.services.decoradores_factura import bloquear_si_factura_inmutable
from app.services.auditoria_service import auditar
from app.constants.auditoria import EV_FISCAL, RES_OK, RES_ERROR
from app.utils.request_context import get_ip, get_user_agent
from sqlalchemy import func, case
from app.models.auditoria import Auditoria
from app.services.resumen_fiscal_service import calcular_estado_fiscal
from app.constants.auditoria import RES_OK, RES_ERROR
from app.services.verifactu_envio import enviar_a_aeat
from app.services.email_service import run_async, enviar_email_factura_construido
from app.utils.session_empresa import get_empresa_id

router = APIRouter(prefix="/facturas", tags=["Facturas"])

# ========= FACTURAS =========
# ===========================
# LISTADO PRINCIPAL DE FACTURAS
# ===========================
@router.get("", response_class=HTMLResponse)
def facturas_list(
    request: Request,
    estado: str | None = Query(None),
    cliente_id: int | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada")

    query = select(Factura).where(Factura.empresa_id == empresa_id)

    if estado:
        query = query.where(Factura.estado == estado)

    if cliente_id:
        query = query.where(Factura.cliente_id == cliente_id)

    if fecha_desde:
        query = query.where(Factura.fecha >= fecha_desde)

    if fecha_hasta:
        query = query.where(Factura.fecha <= fecha_hasta)

    # -------------------------------
    # Obtener facturas sin imponer orden SQL
    # -------------------------------
    facturas = session.exec(query).all()

    # -------------------------------
    # ORDENACIÓN INTELIGENTE POR NÚMERO
    # -------------------------------
    def parse_numero(numero: str):
        """
        Devuelve una tupla ordenable:
        (
            año (int o 0),
            correlativo (int o 0),
            es_rectificativa (0 normal / 1 rectificativa)
        )
        """
        if not numero:
            return (0, 0, 0)

        num = numero.strip().upper()

        # Detectar rectificativa
        es_rect = num.endswith("R")
        if es_rect:
            num = num[:-1]

        partes = num.split("-")

        year = 0
        correlativo = 0

        # Detectar año (4 dígitos)
        for p in partes:
            if len(p) == 4 and p.isdigit():
                year = int(p)

        # Intentar correlativo
        ultima = partes[-1]
        try:
            correlativo = int(ultima)
        except:
            correlativo = 0

        return (year, correlativo, 1 if es_rect else 0)

    facturas = sorted(facturas, key=lambda f: parse_numero(f.numero or ""))

    # --------------------------------
    # RESTO DEL CÓDIGO IGUAL
    # --------------------------------
    clientes = session.exec(
        select(Cliente)
        .where(Cliente.empresa_id == empresa_id)
        .order_by(Cliente.nombre)
    ).all()

    factura_ids = [f.id for f in facturas]

    auditoria_counts = {}
    resumen_fiscal = {}

    if factura_ids:
        rows = session.exec(
            select(
                Auditoria.entidad_id,
                func.sum(case((Auditoria.resultado == "OK", 1), else_=0)).label("ok"),
                func.sum(case((Auditoria.resultado == "BLOQUEADO", 1), else_=0)).label("bloqueado"),
                func.sum(case((Auditoria.resultado == "ERROR", 1), else_=0)).label("error"),
            )
            .where(Auditoria.entidad == "FACTURA")
            .where(Auditoria.entidad_id.in_(factura_ids))
            .group_by(Auditoria.entidad_id)
        ).all()

        auditoria_counts = {
            r.entidad_id: {
                "ok": r.ok,
                "bloqueado": r.bloqueado,
                "error": r.error,
            }
            for r in rows
        }

    for f in facturas:
        c = auditoria_counts.get(f.id, {"ok": 0, "bloqueado": 0, "error": 0})

        estado_fiscal = calcular_estado_fiscal(**c)

        resumen_fiscal[f.id] = {
            "estado": estado_fiscal,
            **c,
        }

    return templates.TemplateResponse(
        "facturas/list.html",
        {
            "request": request,
            "facturas": facturas,
            "clientes": clientes,
            "auditoria_counts": auditoria_counts or {},
            "resumen_fiscal": resumen_fiscal or {},
            "filtros": {
                "estado": estado,
                "cliente_id": cliente_id,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
            },
        },
    )

@router.get("/form", response_class=HTMLResponse)
def factura_form(
    request: Request,
    session: Session = Depends(get_session),
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    clientes = session.exec(
        select(Cliente)
        .where(Cliente.empresa_id == empresa_id)
        .order_by(Cliente.nombre)
    ).all()

    ivas_db = session.exec(
        select(IVA)
            .where(IVA.activo == True)
            .where(IVA.empresa_id == empresa_id)
            .order_by(IVA.porcentaje)
    ).all()

    # Convertir a JSON serializable
    ivas = [
        {"id": i.id, "porcentaje": i.porcentaje, "descripcion": i.descripcion}
        for i in ivas_db
    ]

    return templates.TemplateResponse(
        "facturas/form.html",
        {
            "request": request,
            "factura": None,
            "lineas": [],
            "clientes": clientes,
            "ivas": ivas,
            "bloqueada": False,
            "modo_editar": False,
        },
    )

# CREAR FACTURA
@router.post("/create")
def factura_create(
    request: Request,
    cliente_id: int = Form(...),
    fecha: date = Form(...),
    iva_global: float = Form(...),
    lineas_json: str = Form(...),
    db: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    if not empresa_id:
        raise HTTPException(
            status_code=400,
            detail="No hay empresa activa. No se puede crear factura."
        )

    if not cliente_id or cliente_id == 0:
        raise HTTPException(status_code=400, detail="Debe seleccionar un cliente válido.")

    # 1) Parsear líneas JSON
    try:
        lineas_data = json.loads(lineas_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Formato de líneas no válido")

    if not isinstance(lineas_data, list):
        raise HTTPException(status_code=400, detail="Las líneas deben ser una lista")

    # 2) Crear factura
    factura = Factura(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        fecha=fecha,
        estado="BORRADOR",
        iva_global=iva_global,
    )

    db.add(factura)
    db.flush()

    subtotal = 0.0
    iva_total = 0.0

    # 3) Crear líneas
    for linea in lineas_data:
        descripcion = (linea.get("descripcion") or "").strip()
        if not descripcion:
            continue

        cantidad = float(linea.get("cantidad") or 0)
        precio_unitario = float(linea.get("precio_unitario") or 0)

        base = cantidad * precio_unitario
        importe_iva = base * iva_global / 100.0

        subtotal += base
        iva_total += importe_iva

        db.add(
            LineaFactura(
                factura_id=factura.id,
                descripcion=descripcion,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total=base + importe_iva,
                concepto_id=linea.get("concepto_id") or None,
            )
        )

    factura.subtotal = round(subtotal, 2)
    factura.iva_total = round(iva_total, 2)
    factura.total = round(subtotal + iva_total, 2)

    db.add(factura)
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)

@router.get("/{factura_id}/edit", response_class=HTMLResponse)
def factura_edit(
    factura_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    lineas_db = session.exec(
        select(LineaFactura).where(LineaFactura.factura_id == factura_id)
    ).all()

    lineas = [
        {
            "id": l.id,
            "descripcion": l.descripcion,
            "cantidad": l.cantidad,
            "precio_unitario": l.precio_unitario,
            "total": l.total,
            "concepto_id": l.concepto_id,   # <<< NUEVO
        }
        for l in lineas_db
    ]

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    clientes = session.exec(
        select(Cliente)
        .where(Cliente.empresa_id == empresa_id)
        .order_by(Cliente.nombre)
    ).all()


    # IVA global
    ivas_db = session.exec(
        select(IVA)
            .where(IVA.activo == True)
            .where(IVA.empresa_id == empresa_id)
            .order_by(IVA.porcentaje)
    ).all()

    ivas = [
        {"id": i.id, "porcentaje": i.porcentaje, "descripcion": i.descripcion}
        for i in ivas_db
    ]

    return templates.TemplateResponse(
        "facturas/form.html",
        {
            "request": request,
            "factura": factura,
            "lineas": lineas,
            "clientes": clientes,
            "ivas": ivas,
            "bloqueada": (factura.estado.upper() == "VALIDADA"),
            "modo_editar": True,
        },
    )

@router.post("/{factura_id}/edit")
@bloquear_si_factura_inmutable()
def factura_edit_save(request: Request,
    factura_id: int,
    cliente_id: int = Form(...),
    fecha: date | None = Form(None),
    lineas_json: str = Form(...),
    iva_global: float = Form(...),
    session: Session = Depends(get_session),
):

    if fecha is None:
        fecha = date.today()

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    bloquear_edicion_factura(factura, session)

    if fecha:
        validar_fecha_factura(fecha, session)

    factura.cliente_id = cliente_id
    factura.fecha = fecha
    factura.iva_global = iva_global

    lineas_data = json.loads(lineas_json)
    existentes = {linea.id: linea for linea in factura.lineas}

    subtotal = 0.0

    for l in lineas_data:
        desc = (l.get("descripcion") or "").strip()
        if not desc:
            continue

        cantidad = float(l.get("cantidad") or 0)
        precio = float(l.get("precio_unitario") or 0)

        base = cantidad * precio
        subtotal += base

        linea_id = l.get("id")

        if linea_id and linea_id in existentes:
            # editar
            linea = existentes[linea_id]
            linea.descripcion = desc
            linea.cantidad = cantidad
            linea.precio_unitario = precio
            linea.total = base
            linea.concepto_id = l.get("concepto_id") or None
            existentes.pop(linea_id)

        else:
            # nueva línea
            nueva = LineaFactura(
                factura_id=factura.id,
                descripcion=desc,
                cantidad=cantidad,
                precio_unitario=precio,
                total=base,
                concepto_id=l.get("concepto_id") or None,
            )
            session.add(nueva)

    # Borrar líneas eliminadas en UI
    for linea_no_enviada in existentes.values():
        session.delete(linea_no_enviada)

    # Totales
    factura.subtotal = round(subtotal, 2)
    factura.iva_total = round(subtotal * (iva_global / 100), 2)
    factura.total = factura.subtotal + factura.iva_total

    session.add(factura)
    session.commit()



    return RedirectResponse("/facturas", status_code=303)

@router.get("/{factura_id}/preview-validacion")
def factura_preview_validacion(request: Request,
    factura_id: int,
    fecha: date = Query(...),
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    # Última factura validada
    ultima = session.exec(
        select(Factura)
        .where(Factura.estado == "VALIDADA")
        .where(Factura.empresa_id == empresa_id)
        .order_by(Factura.fecha.desc())
    ).first()

    if ultima:
        fecha_minima = ultima.fecha
    else:
        fecha_minima = factura.fecha or date.today()

    fecha_maxima = date.today()

    # Preview numeración
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")
    year = fecha.year

    if emisor.ultimo_anio_numerado != year:
        correlativo = 1
    else:
        correlativo = emisor.siguiente_numero or 1

    numero_preview = f"{year}-{correlativo:04d}"

    return {
        "ok": True,
        "numero": numero_preview,
        "fecha_minima": fecha_minima.isoformat(),
        "fecha_maxima": fecha_maxima.isoformat(),
    }


@router.post("/{factura_id}/validar")
def validar_factura(
    factura_id: int,
    fecha: date = Form(...),
    mensaje_iva: str = Form(""),
    session: Session = Depends(get_session),
    request: Request = None,
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        auditar(

            session,
            entidad="FACTURA",
            entidad_id=factura_id,
            accion="VALIDAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo="Factura no encontrada",
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        return {"ok": False, "error": "Factura no encontrada."}

    if factura.estado == "VALIDADA":
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo="Factura ya validada",
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        return {"ok": False, "error": "La factura ya está validada."}

    # ============================
    # 1) Validar fecha
    # ============================
    try:
        validar_fecha_factura(fecha, session, empresa_id=empresa_id)
    except HTTPException as e:
        # Error de negocio (por ejemplo 403/400)
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo=e.detail,
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        return {"ok": False, "error": e.detail}
    except Exception as e:
        # Error inesperado (500)
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo=str(e),
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        raise

    # ============================
    # 2) NO bloquear por PDF
    # ============================
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")

    ruta_base = (emisor.ruta_pdf or "").strip()

    # ============================
    # 3) Comprobar orden cronológico
    # ============================
    ultima = session.exec(
        select(Factura)
        .where(Factura.estado == "VALIDADA")
        .where(Factura.empresa_id == empresa_id)
        .order_by(Factura.fecha.desc())
    ).first()

    if ultima and fecha < ultima.fecha:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo="Fecha anterior a la última factura validada",
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        return {"ok": False, "error": "Fecha inválida."}

    # ============================
    # 4) Numeración + datos
    # ============================
    numero = generar_numero_factura(session, fecha, empresa_id)
    factura.numero = numero
    factura.fecha = fecha

    mensaje_iva = (mensaje_iva or "").strip()
    if mensaje_iva:
        factura.mensaje_iva = mensaje_iva

    # ============================
    # 5) Recalcular totales
    # ============================
    lineas = session.exec(
        select(LineaFactura).where(LineaFactura.factura_id == factura_id)
    ).all()

    recalcular_totales(factura, lineas)

    # ============================
    # 6) VeriFactu
    # ============================
    try:
        verificar_verifactu(factura, session)
    except HTTPException as e:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo=e.detail,
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        return {"ok": False, "error": e.detail}
    except Exception as e:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo=str(e),
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        raise

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    # ============================
    # 7) Validar definitivamente
    # ============================
    factura.estado = "VALIDADA"
    factura.fecha_validacion = date.today()

    try:
        bloquear_numeracion(session, fecha, empresa_id)
    except HTTPException as e:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo=e.detail,
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        session.rollback()
        return {"ok": False, "error": e.detail}
    except Exception as e:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="VALIDAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo=str(e),
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
        session.rollback()
        raise

    session.add(factura)
    session.commit()
    session.refresh(factura)

    # ============================
    # 8) Generar PDF
    # (NO dependemos de ruta servidor)
    # ============================
    try:
        generar_factura_pdf(
            factura=factura,
            lineas=lineas,
            ruta_base=ruta_base,   # local → guarda; Render → buffer
            emisor=emisor,
            config=config,
            incluir_mensaje_iva=True,
        )
    except Exception as e:
        # IMPORTANTE: el PDF NO debe bloquear validación fiscal
        # Solo auditamos aviso
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura.id,
            accion="PDF",
            resultado="ERROR",
            nivel_evento="WARN",
            motivo=f"PDF no generado: {e}",
            ip=get_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )

    # ============================
    # 9) Auditoría final OK
    # ============================
    auditar(
        session,
        entidad="FACTURA",
        entidad_id=factura.id,
        accion="VALIDAR",
        resultado="OK",
        nivel_evento="FISCAL",
        ip=get_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None,
    )

    return {
        "ok": True,
        "id": factura.id,
        "numero": numero
    }

@router.get("/min-date")
def factura_min_date(request: Request, session: Session = Depends(get_session)):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    f = session.exec(
        select(Factura)
            .where(Factura.estado == "VALIDADA")
            .where(Factura.empresa_id == empresa_id)
            .order_by(Factura.fecha.desc())
    ).first()

    if not f:
        # Si no hay ninguna validada -> se permite cualquier fecha (hoy)
        return {"min_date": date.today().isoformat()}

    # La siguiente factura debe tener una fecha >= última validada
    min_date = f.fecha.isoformat()

    return {"min_date": min_date}

@router.get("/next-number")
def factura_next_number(request: Request,
    fecha: date = Query(default=None),
    session: Session = Depends(get_session),
):
    if fecha is None:
        fecha = date.today()

    year = fecha.year

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()
    if not emisor:
        raise HTTPException(
            status_code=400,
            detail="No existe configuración del emisor. Configure el sistema antes de emitir facturas."
        )

    # ============================
    # Última factura VALIDADA del año
    # ============================
    ultima = session.exec(
        select(Factura)
        .where(Factura.estado == "VALIDADA")
        .where(Factura.empresa_id == emisor.empresa_id)
        .where(Factura.numero.like(f"%{year}-%"))
        .order_by(Factura.numero.desc())
    ).first()

    if not ultima or not ultima.numero:
        correlativo = 1
    else:
        try:
            parte_final = ultima.numero.split("-")[-1]
            solo_numero = re.sub(r"\D", "", parte_final)
            correlativo = int(solo_numero) + 1
        except:
            correlativo = 1

    # ============================
    # Formatos
    # ============================
    if emisor.modo_numeracion == "BASICO":
        numero = f"{year}-{correlativo:04d}"

    elif emisor.modo_numeracion == "SERIE":
        serie = (emisor.serie_facturacion or "A").upper()
        numero = f"{serie}-{year}-{correlativo:04d}"

    else:
        raise HTTPException(
            400, "Modo de numeración del emisor no válido"
        )

    return {
        "ok": True,
        "numero": numero
    }


@router.get("/{factura_id}/generar-pdf", response_class=HTMLResponse)
def factura_generar_pdf(factura_id: int, request: Request, session: Session = Depends(get_session)):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    lineas = session.exec(
        select(LineaFactura).where(LineaFactura.factura_id == factura_id)
    ).all()

    # ============================
    # 1) Emisor + Config
    # ============================
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")

    ruta_base = (emisor.ruta_pdf or "").strip()

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    # ============================
    # 2) Generar PDF
    # ============================
    try:
        pdf_output, filename = generar_factura_pdf(
            factura=factura,
            lineas=lineas,
            ruta_base=ruta_base,      # LOCAL → fichero | RENDER → ignorado
            emisor=emisor,
            config=config,
            incluir_mensaje_iva=True,
        )
    
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "mensaje": "No fue posible generar el PDF de la factura.",
                "solucion": str(e),
            }
        )

    # ============================
    # 3) Respuesta según entorno
    # ============================
    # Caso A → estamos en local y se guardó fichero físico
    if isinstance(pdf_output, str) and os.path.isfile(pdf_output):
        factura.ruta_pdf = pdf_output
        session.add(factura)
        session.commit()

    # Caso B → Render u otro entorno: BytesIO → Descargar al usuario
    from fastapi.responses import StreamingResponse

    pdf_output.seek(0)

    return StreamingResponse(
        pdf_output,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.get("/{factura_id}/delete", response_class=HTMLResponse)
@bloquear_si_factura_inmutable()
def factura_delete(request: Request,
    factura_id: int,
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    # Si usas lógica de negocio adicional
    bloquear_borrado_factura(factura, session)

    # ============================
    # Eliminar líneas asociadas
    # ============================
    session.exec(
        delete(LineaFactura).where(LineaFactura.factura_id == factura_id)
    )

    # ============================
    # Eliminar la factura
    # ============================
    session.delete(factura)

    # ============================
    # Confirmar cambios
    # ============================
    session.commit()

    return RedirectResponse("/facturas", status_code=303)

@router.post("/{factura_id}/anular")
def factura_anular(
    factura_id: int,
    request: Request,
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")
    if not factura:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura_id,
            accion="ANULAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo="Factura no encontrada",
            ip=get_ip(request),
            user_agent=get_user_agent(request),
        )
        return {"ok": False, "error": "Factura no encontrada."}
    
    if factura.estado != "VALIDADA":
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura_id,
            accion="ANULAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo="Factura no válida para anulación",
            ip=get_ip(request),
            user_agent=get_user_agent(request),
        )
        return {"ok": False, "error": "Solo se pueden anular facturas validadas."}    

    # ============================
    # 1) Verificar ruta PDFs
    # ============================
    # Ruta y textos del emisor
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")
    ruta_base = (emisor.ruta_pdf or "").strip()

    

    # ========= MENSAJE LEGAL RECTIFICATIVA =========
    texto_rect = (emisor.texto_rectificativa or "").strip()

    if not texto_rect:
        texto_rect = (
            "Factura rectificativa emitida conforme al Art. 89 de la Ley 37/1992 del IVA. "
            f"Esta rectificación afecta a la factura original Nº {factura.numero} de fecha "
            f"{factura.fecha.strftime('%d/%m/%Y')}, dejando sin efecto sus importes."
        )

    # ============================
    # 2) Marcar ORIGINAL como ANULADA
    # ============================
    factura.estado = "ANULADA"
    session.add(factura)

    # ============================
    # 2. Verificar si ya existe rectificativa
    # ============================
    numero_rect = f"{factura.numero}R"
    

    existe = session.exec(
        select(Factura)
            .where(Factura.numero == numero_rect)
            .where(Factura.empresa_id == empresa_id)
    ).first()

    if existe:
        return {"ok": False, "error": "Ya existe una rectificativa para esta factura."}

    # ============================
    # 3) Crear RECTIFICATIVA
    # ============================
    rect = Factura(
        empresa_id=factura.empresa_id,
        cliente_id=factura.cliente_id,
        fecha=date.today(),
        numero=numero_rect,
        estado="VALIDADA",
        subtotal=0,
        iva_total=0,
        total=0,
        iva_global=factura.iva_global,
    )
    session.add(rect)
    session.flush()

    rect.mensaje_iva = texto_rect

    # ============================
    # 4) Crear líneas negativas
    # ============================
    iva_factura = factura.iva_global or 0
    originales = session.exec(
        select(LineaFactura).where(LineaFactura.factura_id == factura.id)
    ).all()

    subtotal = iva_total = 0
    lineas_rect = []

    for l in originales:
        base = l.cantidad * l.precio_unitario
        iva_calc = base * iva_factura / 100

        nueva = LineaFactura(
            factura_id=rect.id,
            descripcion=f"(Rectific.) {l.descripcion}",
            cantidad=-l.cantidad,
            precio_unitario=l.precio_unitario,
            total=-(base + iva_calc),
            concepto_id=l.concepto_id
        )

        subtotal += -base
        iva_total += -iva_calc
        session.add(nueva)
        lineas_rect.append(nueva)

    rect.subtotal = round(subtotal, 2)
    rect.iva_total = round(iva_total, 2)
    rect.total = round(subtotal + iva_total, 2)

    session.commit()

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    # ============================
    # 5) GENERAR PDF (solo local si procede)
    # ============================
    if ruta_base and os.path.isdir(ruta_base) and os.access(ruta_base, os.W_OK):
        try:
            generar_factura_pdf(
                factura=rect,
                lineas=lineas_rect,
                ruta_base=ruta_base,
                emisor=emisor,
                config=config,
                incluir_mensaje_iva=True,
            )
        except Exception as e:
            # No rompemos anulación fiscal si falla el PDF
            pass

    auditar(
        session,
        entidad="FACTURA",
        entidad_id=factura.id,
        accion="ANULAR",
        resultado="OK",
        nivel_evento="FISCAL",
        ip=get_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None,
    )


    return {"ok": True, "rectificativa_id": rect.id, "numero": rect.numero}

@router.post("/{factura_id}/rectificar")
def factura_rectificar(
    factura_id: int,
    request: Request,
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")
    if not factura:
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura_id,
            accion="RECTIFICAR",
            resultado="ERROR",
            nivel_evento="ERROR",
            motivo="Factura no encontrada",
            ip=get_ip(request),
            user_agent=get_user_agent(request),
        )
        return {"ok": False, "error": "Factura no encontrada."}

    if factura.estado != "VALIDADA":
        auditar(
            session,
            entidad="FACTURA",
            entidad_id=factura_id,
            accion="RECTIFICAR",
            resultado="BLOQUEADO",
            nivel_evento="FISCAL",
            motivo="Factura no válida para rectificación",
            ip=get_ip(request),
            user_agent=get_user_agent(request),
        )
        return {"ok": False, "error": "Solo se pueden rectificar facturas validadas."}
    
    # ============================
    # Ruta y textos del emisor
    # ============================
    # 2) Comprobar ruta PDF pero NO bloquear si no existe
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")
    ruta_base = (emisor.ruta_pdf or "").strip()

    usar_ruta_servidor = False

    if ruta_base and os.path.isdir(ruta_base) and os.access(ruta_base, os.W_OK):
        usar_ruta_servidor = True

    # ========= MENSAJE LEGAL RECTIFICATIVA =========
    texto_rect = (emisor.texto_rectificativa or "").strip()

    if not texto_rect:
        texto_rect = (
            "Factura rectificativa emitida conforme al Art. 89 de la Ley 37/1992 del IVA. "
            f"Esta rectificación afecta a la factura original Nº {factura.numero} de fecha "
            f"{factura.fecha.strftime('%d/%m/%Y')}, dejando sin efecto sus importes."
        )

    # Nueva rectificativa
    numero_rect = f"{factura.numero}R"

    rect = Factura(
        empresa_id=factura.empresa_id,   # 🔥 HEREDA EMPRESA
        cliente_id=factura.cliente_id,
        fecha=date.today(),
        numero=numero_rect,
        estado="VALIDADA",
        subtotal=0,
        iva_total=0,
        total=0,
        iva_global=factura.iva_global
    )
    session.add(rect)
    session.flush()

    # Inserta el mensaje legal en la factura rectificativa
    rect.mensaje_iva = texto_rect

    # IVA GLOBAL original
    iva_factura = factura.iva_global or 0

    originales = session.exec(
        select(LineaFactura).where(LineaFactura.factura_id == factura.id)
    ).all()

    subtotal = iva_total = 0
    lineas_rect = []

    for l in originales:
        base = l.cantidad * l.precio_unitario
        iva_calc = base * iva_factura / 100

        nueva = LineaFactura(
            factura_id=rect.id,
            descripcion=f"(Rectific.) {l.descripcion}",
            cantidad=-l.cantidad,
            precio_unitario=l.precio_unitario,
            total=-(base + iva_calc),
            concepto_id=l.concepto_id
        )

        subtotal += -base
        iva_total += -iva_calc

        session.add(nueva)
        lineas_rect.append(nueva)

    rect.subtotal = round(subtotal, 2)
    rect.iva_total = round(iva_total, 2)
    rect.total = round(subtotal + iva_total, 2)
    session.commit()
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    # ============================
    # PDF (solo local si existe ruta válida)
    # ============================
    if ruta_base and os.path.isdir(ruta_base) and os.access(ruta_base, os.W_OK):
        try:
            generar_factura_pdf(
                factura=rect,
                lineas=lineas_rect,
                ruta_base=ruta_base,
                emisor=emisor,
                config=config,
                incluir_mensaje_iva=True,
            )
        except Exception:
            # El fallo del PDF NO puede invalidar la operación fiscal
            pass

    auditar(
        session,
        entidad="FACTURA",
        entidad_id=factura.id,
        accion="RECTIFICAR",
        resultado="OK",
        nivel_evento="FISCAL",
        ip=get_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None,
    )

    return {"ok": True, "rectificativa_id": rect.id, "numero": rect.numero}

@router.post("/{factura_id}/prevalidar")
def factura_pre_validar(request: Request,
    factura_id: int,
    fecha: date = Form(...),
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")


    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")

    iva = factura.iva_global or 0

    mensaje_sugerido = None

    if iva == 0:
        mensaje_sugerido = emisor.texto_exento or "Operación exenta de IVA según Ley 37/1992."

    elif iva <= 10:
        mensaje_sugerido = emisor.mensaje_iva or "IVA reducido según normativa vigente."

    if mensaje_sugerido is None:
        return {"ok": True, "necesita_modal": False}

    return {
        "ok": True,
        "necesita_modal": True,
        "mensaje_iva_sugerido": mensaje_sugerido,
    }


# ========= FIN FACTURAS =========


@router.post("/{factura_id}/email")
async def enviar_factura_email(request: Request,
    factura_id: int,
    data: dict = Body(...),
    session: Session = Depends(get_session)
):

    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    factura = session.get(Factura, factura_id)
    if not factura or factura.empresa_id != empresa_id:
        raise HTTPException(404, "Factura no encontrada")

    para = (data.get("para") or "").strip()
    asunto = (data.get("asunto") or "").strip()
    cuerpo = (data.get("cuerpo") or "").strip()
    cc_raw = data.get("cc")
    adjuntar_pdf = data.get("adjuntar_pdf", True)

    if not para:
        raise HTTPException(400, "Debe indicar un destinatario")
    if not asunto:
        raise HTTPException(400, "Debe indicar asunto")

    cc_list = []
    if cc_raw:
        if isinstance(cc_raw, str):
            cc_list = [c.strip() for c in cc_raw.split(",") if c.strip()]
        elif isinstance(cc_raw, list):
            cc_list = [c.strip() for c in cc_raw if c.strip()]

    # =========================
    # Guardar registro envío
    # =========================
    session.add(
        EnviosEmail(
            factura_id=factura_id,
            destinatario=para,
            cc=", ".join(cc_list) if cc_list else None,
            asunto=asunto,
            cuerpo=cuerpo,
        )
    )
    session.commit()


    # =========================
    # PREPARAR TODO ANTES DEL HILO
    # =========================
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    emisor = session.exec(
        select(Emisor).where(Emisor.empresa_id == empresa_id)
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración del emisor para esta empresa")


    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    if not emisor:
        raise HTTPException(400, "No hay configuración de emisor")
    if not config:
        raise HTTPException(400, "No hay configuración del sistema")

    pdf_path = None

    if adjuntar_pdf:
        from app.services.facturas_pdf import generar_factura_pdf
        import tempfile
        import os

        ruta_base = (emisor.ruta_pdf or "").strip()

        # ============================
        # 1) Si hay carpeta local válida → úsala
        # ============================
        if ruta_base and os.path.isdir(ruta_base) and os.access(ruta_base, os.W_OK):
            ruta_fisica, _ = generar_factura_pdf(
                factura=factura,
                lineas=factura.lineas,
                ruta_base=ruta_base,
                emisor=emisor,
                config=config,
                incluir_mensaje_iva=True,
            )
            pdf_path = ruta_fisica

        else:
            # ============================
            # 2) Servidor / sin ruta → generar PDF temporal
            # ============================
            tmp_dir = tempfile.gettempdir()
            tmp_file = os.path.join(
                tmp_dir,
                f"factura_{factura.id or 'tmp'}.pdf"
            )

            generar_factura_pdf(
                factura=factura,
                lineas=factura.lineas,
                ruta_base=tmp_dir,
                emisor=emisor,
                config=config,
                incluir_mensaje_iva=True,
                nombre_personalizado=os.path.basename(tmp_file)
            )

            pdf_path = tmp_file


    # =========================
    # 🚀 AHORA SÍ THREAD SIN BD
    # =========================
    run_async(
        enviar_email_factura_construido,
        smtp_config={
            "host": config.smtp_host,
            "port": config.smtp_port,
            "user": config.smtp_user,
            "password": config.smtp_password,
            "ssl": config.smtp_ssl,
            "tls": config.smtp_tls,
        },
        para=para,
        asunto=asunto,
        cuerpo=cuerpo,
        cc=cc_list,
        pdf_path=pdf_path,
        remitente=config.smtp_user
    )

    return {"ok": True, "mensaje": "Email en proceso de envío"}


@router.get("/offline", response_class=HTMLResponse)
def facturas_offline_view(request: Request):
    # No hace falta BD, solo plantilla
    return templates.TemplateResponse(
        "facturas/offline.html",
        {"request": request},
    )