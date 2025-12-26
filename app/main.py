from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
from sqlmodel import Session, select
from app.core.templates import templates
from fastapi.responses import FileResponse

from app.db.session import engine
from app.db.base import init_db

# =========================
# MODELOS BASE
# =========================
from app.models.emisor import Emisor
from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.empresa import Empresa
from app.models.user import User

# =========================
# ROUTERS
# =========================
from app.routers.dashboard import router as dashboard_router
from app.routers.clientes import router as clientes_router
from app.routers.conceptos import router as conceptos_router
from app.routers.facturas import router as facturas_router
from app.routers.configuracion_emisor import router as emisor_router
from app.routers.configuracion_sistema import router as sistema_router
from app.routers.iva import router as iva_router
from app.routers.informes import router as informes_router
from app.routers import auditoria
from app.routers.auth import router as auth_router
from app.routers import pin
from app.routers import auth_recovery
from app.routers import setup
from app.routers.perfil import router as perfil_router
from app.core.templates import templates
from app.routers.facturas_offline import api_router as offline_api_router
from app.routers.offline import router as offline_router
from app.routers import registro
from app.routers import usuarios

router = APIRouter()

# =========================
# MIDDLEWARE
# =========================
from starlette.middleware.sessions import SessionMiddleware
from app.core.auth_middleware import AuthMiddleware
from app.middleware.first_run import FirstRunMiddleware

import os


# ============================================================
# APP
# ============================================================
app = FastAPI(title="Sistema de Facturación")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-session-key")


# ============================================================
# MIDDLEWARE → ORDEN CORRECTO
# ============================================================
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="factura_session",
    same_site="lax",
    https_only=False,
    max_age=3600,
)

app.add_middleware(FirstRunMiddleware)
app.add_middleware(AuthMiddleware)

# ============================================================
# PDF + STATIC
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PDF_ROOT = BASE_DIR / "facturas_pdf"
PDF_ROOT.mkdir(exist_ok=True)

app.mount("/pdf", StaticFiles(directory=PDF_ROOT), name="pdf")


# ============================================================
# UPLOADS
# ============================================================
UPLOADS_DIR = Path("app/static/uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
def on_startup():
    init_db()

    with Session(engine) as session:
        # =========================
        # EMPRESA BASE solo si no existe ninguna
        # =========================
        empresa = session.exec(select(Empresa)).first()
        if not empresa:
            empresa = Empresa(
                nombre="Empresa Principal",
                cif="N/A",
                activa=True
            )
            session.add(empresa)
            session.flush()  # para obtener empresa.id

        empresa_id = empresa.id

        # =========================
        # EMISOR LIGADO A EMPRESA
        # =========================
        emisor = session.exec(
            select(Emisor).where(Emisor.empresa_id == empresa_id)
        ).first()

        if not emisor:
            emisor = Emisor(
                empresa_id=empresa_id
            )
            session.add(emisor)

        # =========================
        # CONFIG POR EMPRESA
        # =========================
        config = session.exec(
            select(ConfiguracionSistema).where(
                ConfiguracionSistema.empresa_id == empresa_id
            )
        ).first()

        if not config:
            config = ConfiguracionSistema(empresa_id=empresa_id)
            session.add(config)

        session.commit()

    print(">>> Sistema listo")

@app.get("/")
async def root():
    return RedirectResponse("/dashboard")

@app.get("/offline")
async def offline(request: Request):
    return templates.TemplateResponse("offline.html", {"request": request})


# ============================================================
# CONTEXTO GLOBAL JINJA
# ============================================================
from app.core.auth_utils import get_user_safe
templates.env.globals["get_user"] = get_user_safe


from jinja2 import contextfunction

@contextfunction
def get_emisor_logo(context):
    try:
        request = context.get("request")
        if not request:
            return None

        empresa_id = request.session.get("empresa_id")
        if not empresa_id:
            return None

        with Session(engine) as db:
            emisor = db.exec(
                select(Emisor).where(Emisor.empresa_id == empresa_id)
            ).first()

            if emisor and emisor.logo_path:
                return f"/static/{emisor.logo_path.lstrip('/')}"

        return None
    except:
        return None

templates.env.globals["get_emisor_logo"] = get_emisor_logo


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse("app/static/sw.js", media_type="application/javascript")

# ============================================================
# ROUTERS
# ============================================================
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(clientes_router)
app.include_router(conceptos_router)
app.include_router(facturas_router)
app.include_router(emisor_router)
app.include_router(sistema_router)
app.include_router(iva_router)
app.include_router(informes_router)
app.include_router(auditoria.router)
app.include_router(pin.router)
app.include_router(setup.router)
app.include_router(auth_recovery.router)
app.include_router(perfil_router)
app.include_router(offline_api_router)
app.include_router(offline_router)
app.include_router(registro.router)
app.include_router(usuarios.router)

