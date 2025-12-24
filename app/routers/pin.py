from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from app.db.session import get_session, Session
from app.models.emisor import Emisor
from fastapi.templating import Jinja2Templates
from datetime import datetime

from app.core.templates import templates

router = APIRouter()


@router.get("/pin")
async def pin_page(request: Request):
    return templates.TemplateResponse(
        "auth/pin.html",
        {"request": request}
    )


@router.post("/pin")
async def validar_pin(
    request: Request,
    pin: str = Form(...),
    session: Session = Depends(get_session)
):

    emisor = session.get(Emisor, 1)

    # Si no hay PIN configurado → no bloquear
    if not emisor or not emisor.seguridad_pin:
        return RedirectResponse("/dashboard", status_code=303)

    # Validación
    if pin == emisor.seguridad_pin:

        # Desbloquear
        request.session["pin_pendiente"] = False

        # Reseteamos el contador de inactividad
        request.session["ultimo_acceso"] = datetime.utcnow().isoformat()

        return RedirectResponse("/dashboard", status_code=303)

    # PIN incorrecto
    return templates.TemplateResponse(
        "auth/pin.html",
        {
            "request": request,
            "error": "PIN incorrecto"
        }
    )
