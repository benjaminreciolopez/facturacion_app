from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from datetime import datetime

from app.db.session import get_session
from app.core.security import get_password_hash
from app.core.templates import templates

from app.models.user import User
from app.models.emisor import Emisor
from app.models.empresa import Empresa
from app.models.configuracion_sistema import ConfiguracionSistema

router = APIRouter(tags=["Registro"])


@router.get("/registro")
def registro_form(request: Request):
    return templates.TemplateResponse(
        "registro.html",
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
    # VALIDAR NOMBRE EMPRESA
    # ============================

    existe_nombre = session.exec(
        select(Empresa).where(Empresa.nombre == nombre_empresa.strip())
    ).first()

    if existe_nombre:
        return templates.TemplateResponse(
            "registro.html",
            {"request": request, "error": "Ya existe una empresa con ese nombre"},
            status_code=400,
        )

    # =============================
    # VALIDAR EMAIL
    # =============================
    existe_user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if existe_user:
        return templates.TemplateResponse(
            "registro.html",
            {"request": request, "error": "Ese email ya está registrado"},
            status_code=400,
        )

    # =============================
    # VALIDAR CIF (solo si se envía)
    # =============================
    cif = (cif or "").strip() or None

    if cif:
        existe_empresa = session.exec(
            select(Empresa).where(Empresa.cif == cif)
        ).first()

        if existe_empresa:
            return templates.TemplateResponse(
                "registro.html",
                {
                    "request": request,
                    "error": "Ya existe una empresa con ese CIF",
                },
                status_code=400,
            )

    # =============================
    # CREAR EMPRESA
    # =============================
    empresa = Empresa(
        nombre=nombre_empresa.strip(),
        cif=cif,
        activa=True,
    )
    session.add(empresa)
    session.flush()  # obtener empresa.id

    # =============================
    # CREAR ADMIN
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
    config_existing = session.exec(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.empresa_id == empresa.id
        )
    ).first()

    if not config_existing:
        config = ConfiguracionSistema(
            empresa_id=empresa.id,
            actualizado_en=datetime.utcnow(),
        )
        session.add(config)

    # =============================
    # CREAR EMISOR BASE
    # =============================

    emisor = Emisor(
        empresa_id=empresa.id,
        nombre=nombre_empresa.strip(),
        nif=cif,
    )
    session.add(emisor)

    session.commit()

    return RedirectResponse("/login", status_code=302)
