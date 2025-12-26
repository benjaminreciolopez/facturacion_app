from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.user import User
from app.core.security import get_password_hash
from app.models.configuracion_sistema import ConfiguracionSistema
from datetime import datetime


router = APIRouter(tags=["Setup"])
from app.core.templates import templates


@router.get("/setup")
def setup_form(request: Request, session: Session = Depends(get_session)):

    existe = session.exec(select(User)).first()
    if existe:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        "setup/first_user.html",
        {"request": request, "error": None}
    )


@router.post("/setup")
def setup_create(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    pin: str | None = Form(None),
    session: Session = Depends(get_session),
):
    # Si ya existe algún usuario → no permitir setup
    existe = session.exec(select(User)).first()
    if existe:
        return RedirectResponse("/", status_code=302)

    # =========================
    # EMPRESA BASE
    # =========================
    from app.models.empresa import Empresa

    empresa = session.get(Empresa, 1)
    if not empresa:
        empresa = Empresa(
            id=1,
            nombre="Empresa Principal",
            cif="N/A",
            activa=True
        )
        session.add(empresa)
        session.flush()

    # =========================
    # CREAR ADMIN
    # =========================
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        rol="admin",
        activo=True,
        empresa_id=1,
    )

    if pin:
        user.pin_hash = get_password_hash(pin)

    session.add(user)
    # =========================
    # CONFIG SISTEMA BÁSICA
    # =========================
    empresa_id = empresa.id

    config = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa_id
        )
    ).first()

    if not config:
        config = ConfiguracionSistema(
            empresa_id=empresa_id,
            actualizado_en=datetime.utcnow()
        )
        session.add(config)

    session.commit()
    return RedirectResponse("/login", status_code=302)
