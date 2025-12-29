from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.templates import templates
from app.models.iva import IVA
from app.utils.session_empresa import get_empresa_id

router = APIRouter(prefix="/configuracion/iva", tags=["IVA"])


# ============================================================
# LISTADO IVA (VISTA)
# ============================================================
@router.get("", response_class=HTMLResponse)
def iva_list_view(
    request: Request,
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión sin empresa activa")

    ivas = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .where(IVA.empresa_id == empresa_id)
        .order_by(IVA.porcentaje)
    ).all()

    return templates.TemplateResponse(
        "configuracion/iva/list.html",
        {
            "request": request,
            "ivas": ivas,
        },
    )


# ============================================================
# LISTADO IVA (JSON)
# ============================================================
@router.get("/list-json", response_class=JSONResponse)
def iva_list_json(
    request: Request,
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión sin empresa activa")

    ivas = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .where(IVA.empresa_id == empresa_id)
        .order_by(IVA.porcentaje)
    ).all()

    return [
        {
            "id": i.id,
            "porcentaje": i.porcentaje,
            "descripcion": i.descripcion,
        }
        for i in ivas
    ]


# ============================================================
# CREAR IVA
# ============================================================
@router.post("/create")
def iva_create(
    request: Request,
    porcentaje: float = Form(...),
    descripcion: str = Form(""),
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión sin empresa activa")

    porcentaje = round(float(porcentaje), 2)

    if porcentaje < 0 or porcentaje > 100:
        return RedirectResponse(
            "/configuracion/iva?error=Porcentaje%20no%20válido",
            status_code=303,
        )

    # evitar duplicado en la misma empresa
    existe = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .where(IVA.empresa_id == empresa_id)
        .where(IVA.porcentaje == porcentaje)
    ).first()

    if existe:
        return RedirectResponse(
            f"/configuracion/iva?error=Ya%20existe%20un%20IVA%20del%20{porcentaje}%",
            status_code=303,
        )

    iva = IVA(
        porcentaje=porcentaje,
        descripcion=(descripcion or "").strip(),
        activo=True,
        empresa_id=empresa_id,
    )

    session.add(iva)
    session.commit()

    return RedirectResponse(
        "/configuracion/iva?ok=IVA%20creado%20correctamente",
        status_code=303,
    )


# ============================================================
# DESACTIVAR IVA
# ============================================================
@router.get("/{iva_id}/delete")
def iva_delete(
    request: Request,
    iva_id: int,
    session: Session = Depends(get_session),
):
    empresa_id = get_empresa_id(request)
    if not empresa_id:
        raise HTTPException(401, "Sesión sin empresa activa")

    iva = session.get(IVA, iva_id)

    if iva and iva.empresa_id == empresa_id:
        iva.activo = False
        session.commit()

    return RedirectResponse("/configuracion/iva", status_code=303)
