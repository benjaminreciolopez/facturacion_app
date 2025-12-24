from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.templates import templates
from app.models.cliente import Cliente

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# LISTADO CLIENTES
@router.get("", response_class=HTMLResponse)
def clientes_view(
    request: Request,
    session: Session = Depends(get_session)
):
    clientes = session.exec(select(Cliente).order_by(Cliente.nombre)).all()

    return templates.TemplateResponse(
        "clientes/list.html",
        {"request": request, "clientes": clientes}
    )


# BUSQUEDA AJAX
@router.get("/search", response_class=HTMLResponse)
def clientes_search(
    request: Request,
    q: str = "",
    session: Session = Depends(get_session),
):
    query = select(Cliente)

    if q:
        q_like = f"%{q.lower()}%"
        query = query.where(
            Cliente.nombre.ilike(q_like) |
            Cliente.nif.ilike(q_like) |
            Cliente.email.ilike(q_like)
        )

    clientes = session.exec(query.order_by(Cliente.nombre)).all()

    return templates.TemplateResponse(
        "clientes/tabla.html",
        {"request": request, "clientes": clientes}
    )

# AUTOCOMPLETE CLIENTES (JSON)
@router.get("/autocomplete")
def clientes_autocomplete(q: str = "", session: Session = Depends(get_session)):

    if not q:
        return []

    q_like = f"%{q.lower()}%"

    clientes = session.exec(
        select(Cliente)
        .where(Cliente.nombre.ilike(q_like))
        .order_by(Cliente.nombre)
        .limit(20)
    ).all()

    return [{"id": c.id, "nombre": c.nombre} for c in clientes]

# FORMULARIO NUEVO CLIENTE
@router.get("/form", response_class=HTMLResponse)
def cliente_form(request: Request):
    return templates.TemplateResponse(
        "clientes/form.html",
        {"request": request, "cliente": None}
    )


# CREAR CLIENTE
@router.post("/create")
def clientes_create(
    request: Request,
    nombre: str = Form(...),
    nif: str = Form(""),
    email: str = Form(""),
    telefono: str = Form(""),
    direccion: str = Form(""),
    poblacion: str = Form(""),
    cp: str = Form(""),
    provincia: str = Form(""),
    pais: str = Form("España"),
    session: Session = Depends(get_session),
):
    # ⚠️ Empresa activa obligatoria
    empresa_id = request.session.get("empresa_id")

    if not empresa_id:
        raise HTTPException(
            status_code=400,
            detail="No hay empresa activa. No se puede crear cliente."
        )

    nuevo = Cliente(
        empresa_id=empresa_id,
        nombre=nombre,
        nif=nif,
        email=email,
        telefono=telefono,
        direccion=direccion,
        poblacion=poblacion,
        cp=cp,
        provincia=provincia,
        pais=pais,
    )

    session.add(nuevo)
    session.commit()

    return RedirectResponse("/clientes", status_code=303)


# EDITAR CLIENTE
@router.get("/{cliente_id}/edit", response_class=HTMLResponse)
def cliente_edit(cliente_id: int, request: Request, session: Session = Depends(get_session)):
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return templates.TemplateResponse(
        "clientes/form.html",
        {"request": request, "cliente": cliente}
    )


# GUARDAR EDICIÓN
@router.post("/{cliente_id}/edit")
def cliente_edit_save(
    cliente_id: int,
    nombre: str = Form(...),
    nif: str = Form(""),
    email: str = Form(""),
    telefono: str = Form(""),
    direccion: str = Form(""),
    poblacion: str = Form(""),
    cp: str = Form(""),
    provincia: str = Form(""),
    pais: str = Form("España"),
    session: Session = Depends(get_session),
):
    cliente = session.get(Cliente, cliente_id)

    cliente.nombre = nombre
    cliente.nif = nif
    cliente.email = email
    cliente.telefono = telefono
    cliente.direccion = direccion
    cliente.poblacion = poblacion
    cliente.cp = cp
    cliente.provincia = provincia
    cliente.pais = pais

    session.add(cliente)
    session.commit()

    return RedirectResponse("/clientes", status_code=303)


# ELIMINAR CLIENTE
@router.get("/{cliente_id}/delete")
def cliente_delete(cliente_id: int, session: Session = Depends(get_session)):
    cliente = session.get(Cliente, cliente_id)
    session.delete(cliente)
    session.commit()

    return RedirectResponse("/clientes", status_code=303)

@router.post("/quick-create")
def clientes_quick_create(
    request: Request,
    nombre: str = Form(...),
    nif: str = Form(""),
    email: str = Form(""),
    telefono: str = Form(""),
    direccion: str = Form(""),
    poblacion: str = Form(""),
    cp: str = Form(""),
    provincia: str = Form(""),
    pais: str = Form("España"),
    session: Session = Depends(get_session),
):
    # Empresa activa obligatoria
    empresa_id = request.session.get("empresa_id")

    if not empresa_id:
        raise HTTPException(
            status_code=400,
            detail="No hay empresa activa. No se puede crear cliente."
        )

    # 1) Duplicado por NIF
    if nif:
        existente = session.exec(
            select(Cliente)
            .where(Cliente.empresa_id == empresa_id)
            .where(Cliente.nif == nif)
        ).first()
        if existente:
            return {"ok": True, "id": existente.id, "nombre": existente.nombre}

    # 2) Duplicado por email
    if email:
        existente = session.exec(
            select(Cliente)
            .where(Cliente.empresa_id == empresa_id)
            .where(Cliente.email == email)
        ).first()
        if existente:
            return {"ok": True, "id": existente.id, "nombre": existente.nombre}

    # 3) Crear cliente
    cliente = Cliente(
        empresa_id=empresa_id,
        nombre=nombre,
        nif=nif or None,
        email=email or None,
        telefono=telefono or None,
        direccion=direccion or None,
        poblacion=poblacion or None,
        cp=cp or None,
        provincia=provincia or None,
        pais=pais or None,
    )

    session.add(cliente)
    session.commit()
    session.refresh(cliente)

    return {"ok": True, "id": cliente.id, "nombre": cliente.nombre}


