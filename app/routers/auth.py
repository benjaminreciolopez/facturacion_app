from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.user import User
from app.core.security import verify_password, create_access_token

router = APIRouter()
from app.core.templates import templates


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None}
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Credenciales incorrectas"},
            status_code=401
        )

    if not user.activo:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Usuario inactivo"},
            status_code=401
        )

    # ========================
    # SESSION LOGIN
    # ========================
    s = request.session
    s.clear()

    s["user"] = {
        "id": user.id,
        "email": user.email,
        "empresa_id": user.empresa_id,
        "rol": user.rol,
    }

    from datetime import datetime
    ahora = datetime.utcnow().isoformat()

    s["ultimo_login"] = ahora
    s["ultimo_acceso"] = ahora
    s["pin_pendiente"] = False

    response = RedirectResponse("/dashboard", status_code=303)
    return response

@router.get("/logout")
def logout(request: Request):
    request.session.clear()

    response = RedirectResponse("/login", status_code=303)

    # Borrar cookie REAL de sesión
    response.delete_cookie("factura_session")

    return response
