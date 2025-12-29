from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
import os

from app.db.session import get_session
from app.models.user import User
from app.models.password_reset import (
    create_password_reset,
    get_password_reset_by_token,
    mark_password_reset_used,
)
from app.core.security import verify_password, get_password_hash
from app.core.templates import templates
from app.services.email_service import send_password_reset_email

router = APIRouter()

APP_URL = os.getenv("APP_URL")

def get_app_url(request: Request):
    if APP_URL:
        return APP_URL.rstrip("/")

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    return str(request.base_url).rstrip("/")


# =========================
# FORMULARIO
# =========================
@router.get("/forgot-password")
def forgot_password_form(request: Request):
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "error": None, "ok": None},
    )


# =========================
# RECUPERACIÓN POR EMAIL
# =========================
@router.post("/forgot-password/email")
def forgot_password_email(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()

    if not user:
        return templates.TemplateResponse(
            "auth/forgot_password.html",
            {"request": request, "error": "Ese email no existe", "ok": None},
        )

    pr = create_password_reset(session=session, email=user.email, hours_valid=1)

    reset_url = f"{APP_URL}/reset-password?token={pr.token}"

    # Enviar correo
    try:
        send_password_reset_email(user.email, reset_url)
        ok_msg = "Te hemos enviado un enlace de recuperación a tu correo."
    except Exception as e:
        print("ERROR SMTP:", e)
        ok_msg = (
            "No hemos podido enviar el correo automáticamente. "
            "Pero puedes usar este enlace manual:"
            f"<br><small>{reset_url}</small>"
        )

    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "error": None, "ok": ok_msg},
    )


# =========================
# FORMULARIO RESET TOKEN
# =========================
@router.get("/reset-password")
def reset_password_form(
    request: Request, token: str, session: Session = Depends(get_session)
):
    pr = get_password_reset_by_token(session, token)

    if not pr or not pr.can_be_used:
        return templates.TemplateResponse(
            "auth/reset_invalid.html", {"request": request}
        )

    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token, "error": None},
    )


# =========================
# CONFIRMAR RESET TOKEN
# =========================
@router.post("/reset-password")
def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    session: Session = Depends(get_session),
):
    pr = get_password_reset_by_token(session, token)

    if not pr or not pr.can_be_used:
        return templates.TemplateResponse(
            "auth/reset_invalid.html",
            {"request": request},
        )

    if password != password2:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "error": "Las contraseñas no coinciden"},
        )

    user = session.exec(select(User).where(User.email == pr.email)).first()
    if not user:
        return templates.TemplateResponse(
            "auth/reset_invalid.html", {"request": request}
        )

    user.password_hash = get_password_hash(password)
    user.requiere_reset = False

    session.add(user)
    mark_password_reset_used(session, pr)

    return RedirectResponse("/login", status_code=303)


# =========================
# RECUPERACIÓN POR PIN
# =========================
@router.post("/forgot-password/pin")
def forgot_password_pin(
    request: Request,
    email: str = Form(...),
    pin: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()

    if not user or not user.pin_hash:
        return templates.TemplateResponse(
            "auth/forgot_password.html",
            {
                "request": request,
                "error": "PIN no disponible para esta cuenta",
                "ok": None,
            },
        )

    if not verify_password(pin, user.pin_hash):
        return templates.TemplateResponse(
            "auth/forgot_password.html",
            {"request": request, "error": "PIN incorrecto", "ok": None},
        )

    return templates.TemplateResponse(
        "auth/reset_password_pin.html",
        {"request": request, "email": user.email},
    )


# =========================
# CONFIRMAR RESET POR PIN
# =========================
@router.post("/reset-password/pin")
def reset_password_pin_confirm(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()

    if not user:
        return RedirectResponse("/forgot-password", status_code=303)

    if password != password2:
        return templates.TemplateResponse(
            "auth/reset_password_pin.html",
            {"request": request, "email": email, "error": "Las contraseñas no coinciden"},
        )

    user.password_hash = get_password_hash(password)
    user.requiere_reset = False

    session.add(user)
    session.commit()

    return RedirectResponse("/login", status_code=303)
