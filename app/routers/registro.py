from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from datetime import datetime

from app.db.session import get_session
from app.core.security import get_password_hash
from app.core.templates import templates

from app.models.user import User
from app.models.empresa import Empresa
from app.models.configuracion_sistema import ConfiguracionSistema

router = APIRouter(tags=["Registro"])


@router.get("/registro")
def registro_form(request: Request):
    return templates.TemplateResponse(
        "auth/registro.html",
        {"request": request, "error": None}
    )


@router.post("/registro")
def registro_submit(
    request: Request,
    nombre_empresa: str = Form(...),
    cif: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):

    # =============================
    # VALIDACIONES
    # =============================
    existe_user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if existe_user:
        return templates.TemplateResponse(
            "auth/registro.html",
            {
                "request": request,
                "error": "Ese email ya está registrado"
            },
            status_code=400
        )

    # =============================
    # CREAR EMPRESA
    # =============================
    empresa = Empresa(
        nombre=nombre_empresa.strip(),
        cif=(cif or "").strip() or None,
        activa=True,
    )

    session.add(empresa)
    session.flush()  # para obtener empresa.id

    # =============================
    # CREAR USUARIO ADMIN
    # =============================
    user = User(
        email=email.strip(),
        password_hash=get_password_hash(password),
        rol="admin",
        activo=True,
        empresa_id=empresa.id,
    )

    session.add(user)

    # =============================
    # CONFIG SISTEMA BÁSICA
    # =============================
    config = ConfiguracionSistema(id=empresa.id)
    config.actualizado_en = datetime.utcnow()

    session.add(config)

    session.commit()

    return RedirectResponse("/login", status_code=302)
