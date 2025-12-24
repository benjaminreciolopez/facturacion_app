from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.templates import templates
from pydantic import BaseModel
from app.services.ai_conceptos import sugerir_nombre_concepto, mejorar_descripcion_concepto
from app.models.concepto import Concepto


router = APIRouter(prefix="/conceptos", tags=["Conceptos"])

# LISTADO PRINCIPAL
@router.get("", response_class=HTMLResponse)
def conceptos_list(
    request: Request,
    session: Session = Depends(get_session)
):
    conceptos = session.exec(
        select(Concepto)
        .where(Concepto.activo == True)
        .order_by(Concepto.nombre)
    ).all()

    return templates.TemplateResponse(
        "conceptos/list.html",
        {"request": request, "conceptos": conceptos}
    )


# BÚSQUEDA AJAX
@router.get("/search", response_class=HTMLResponse)
def conceptos_search(
    request: Request,
    q: str = "",
    session: Session = Depends(get_session)
):
    stmt = select(Concepto).where(Concepto.activo == True)

    if q:
        q_like = f"%{q.lower()}%"
        stmt = stmt.where(
            Concepto.nombre.ilike(q_like) |
            Concepto.descripcion.ilike(q_like)
        )

    conceptos = session.exec(stmt.order_by(Concepto.nombre)).all()

    return templates.TemplateResponse(
        "conceptos/tabla.html",
        {"request": request, "conceptos": conceptos}
    )


# FORMULARIO NUEVO
@router.get("/form", response_class=HTMLResponse)
def concepto_form(request: Request):
    return templates.TemplateResponse(
        "conceptos/form.html",
        {"request": request, "concepto": None}
    )


# CREAR CONCEPTO
@router.post("/create")
def concepto_create(
    nombre: str = Form(...),
    descripcion: str = Form(""),
    session: Session = Depends(get_session)
):
    nuevo = Concepto(
            nombre=nombre,
            descripcion=descripcion,
            activo=True
        )

    session.add(nuevo)

    session.commit()
   
    return RedirectResponse("/conceptos", status_code=303)


# EDITAR CONCEPTO
@router.get("/{concepto_id}/edit", response_class=HTMLResponse)
def concepto_edit(concepto_id: int, request: Request, session: Session = Depends(get_session)):
    concepto = session.get(Concepto, concepto_id)
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    return templates.TemplateResponse(
        "conceptos/form.html",
        {"request": request, "concepto": concepto}
    )

# GUARDAR EDICIÓN
@router.post("/{concepto_id}/edit")
def concepto_edit_save(
    concepto_id: int,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    session: Session = Depends(get_session)
):
    concepto = session.get(Concepto, concepto_id)
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    concepto.nombre = nombre
    concepto.descripcion = descripcion

    session.commit()

    return RedirectResponse("/conceptos", status_code=303)

# ELIMINAR CONCEPTO (hard delete)
@router.post("/{concepto_id}/delete")
def concepto_delete(concepto_id: int, session: Session = Depends(get_session)):
    concepto = session.get(Concepto, concepto_id)
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    session.delete(concepto)
    session.commit()

    return RedirectResponse("/conceptos", status_code=303)


@router.post("/quick-create", response_class=JSONResponse)
def conceptos_quick_create(
    nombre: str = Form(...),
    descripcion: str = Form(""),
    session: Session = Depends(get_session)
):

    # Buscar coincidencia exacta por nombre
    existente = session.exec(
        select(Concepto).where(Concepto.nombre == nombre)
    ).first()

    if existente:
        return JSONResponse(content={
            "ok": True,
            "id": existente.id,
            "nombre": existente.nombre,
            "descripcion": existente.descripcion
        })

    # Crear concepto nuevo
    concepto = Concepto(nombre=nombre, descripcion=descripcion)
    session.add(concepto)
    session.commit()
    session.refresh(concepto)

    return JSONResponse(content={
        "ok": True,
        "id": concepto.id,
        "nombre": concepto.nombre,
        "descripcion": concepto.descripcion
    })


# ---------- IA CONCEPTOS ----------

class SugerirNombrePayload(BaseModel):
    descripcion: str


class SugerirNombreResponse(BaseModel):
    nombre_sugerido: str


@router.post(
    "/ai/sugerir-nombre",
    response_model=SugerirNombreResponse
)
def conceptos_ai_sugerir_nombre(
    payload: SugerirNombrePayload,
):
    nombre = sugerir_nombre_concepto(payload.descripcion)
    return SugerirNombreResponse(nombre_sugerido=nombre)


class MejorarDescripcionPayload(BaseModel):
    descripcion: str
    nombre: str | None = None


class MejorarDescripcionResponse(BaseModel):
    descripcion_mejorada: str


@router.get("/autocomplete", response_class=JSONResponse)
def conceptos_autocomplete(q: str = "", session: Session = Depends(get_session)):

    if not q or len(q) < 2:
        return JSONResponse(content=[])

    q_like = f"%{q.lower()}%"

    conceptos = session.exec(
        select(Concepto)
        .where(Concepto.activo == True)
        .where(
            Concepto.nombre.ilike(q_like) |
            Concepto.descripcion.ilike(q_like)
        )
        .order_by(Concepto.nombre)
        .limit(20)
    ).all()

    return JSONResponse(content=[
        {"id": c.id, "nombre": c.nombre, "descripcion": c.descripcion}
        for c in conceptos
    ])


@router.post("/ai/mejorar-descripcion", response_model=MejorarDescripcionResponse)
def conceptos_ai_mejorar_descripcion(
    payload: MejorarDescripcionPayload,
):
    nueva = mejorar_descripcion_concepto(
        descripcion=payload.descripcion,
        nombre=payload.nombre,
    )
    return MejorarDescripcionResponse(descripcion_mejorada=nueva)
# ---------- FIN IA CONCEPTOS ----------
