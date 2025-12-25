from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select
from pathlib import Path
from datetime import date, datetime, timezone
import os

from app.db.session import get_session
from app.core.templates import templates
from app.models.emisor import Emisor
from app.models.factura import Factura

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

# ⚠️ SOLO PARA USO LOCAL (DESARROLLO)
try:
    from tkinter import Tk
    from tkinter.filedialog import askdirectory
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

router = APIRouter(prefix="/configuracion/emisor", tags=["Emisor"])

# =========================================================
# DIRECTORIOS SEGÚN ENTORNO
# =========================================================
ENV = os.environ.get("ENV", "development")

BASE_DIR = Path(__file__).resolve().parents[2]

if ENV == "production":
    # Render → almacenamiento persistente
    DATA_DIR = Path("/data")
else:
    # Local → carpeta propia del proyecto
    DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Subcarpeta para uploads generales (logo, etc.)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Subcarpeta específica para certificado digital
CERT_DIR = DATA_DIR / "certs"
CERT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# VISTA PRINCIPAL
# =========================================================
@router.get("", response_class=HTMLResponse)
def emisor_view(request: Request, session: Session = Depends(get_session)):

    emisor = session.get(Emisor, 1)
    if not emisor:
        emisor = Emisor(id=1)
        session.add(emisor)
        session.commit()

    year = date.today().year

    existe_validada = session.exec(
        select(Factura)
        .where(Factura.estado == "VALIDADA")
        .where(Factura.fecha.between(date(year, 1, 1), date(year, 12, 31)))
    ).first()

    return templates.TemplateResponse(
        "configuracion/emisor.html",
        {
            "request": request,
            "emisor": emisor,
            "bloqueo_numeracion": existe_validada is not None,
            "env": os.environ.get("ENV", "development"),
        },
    )


# =========================================================
# DATOS GENERALES
# =========================================================
@router.post("/save")
def emisor_save(
    nombre: str = Form(""),
    nif: str = Form(""),
    direccion: str = Form(""),
    poblacion: str = Form(""),
    provincia: str = Form(""),
    cp: str = Form(""),
    pais: str = Form("España"),
    telefono: str = Form(""),
    email: str = Form(""),
    web: str = Form(""),
    session: Session = Depends(get_session),
):
    emisor = session.get(Emisor, 1) or Emisor(id=1)

    emisor.nombre = nombre
    emisor.nif = nif
    emisor.direccion = direccion
    emisor.poblacion = poblacion
    emisor.provincia = provincia
    emisor.cp = cp
    emisor.pais = pais
    emisor.telefono = telefono
    emisor.email = email
    emisor.web = web

    session.add(emisor)
    session.commit()

    return RedirectResponse("/configuracion/emisor", status_code=303)


# =========================================================
# LOGO
# =========================================================
@router.post("/logo")
async def emisor_upload_logo(
    file: UploadFile,
    session: Session = Depends(get_session),
):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    filename = "logo_emisor.png"
    path = UPLOAD_DIR / filename

    with open(path, "wb") as f:
        f.write(await file.read())

    # Guardamos ruta REAL persistente
    emisor.logo_path = str(path)
    session.commit()

    return RedirectResponse("/configuracion/emisor", status_code=303)

@router.post("/logo/eliminar")
async def emisor_eliminar_logo(session: Session = Depends(get_session)):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    if not emisor.logo_path:
        return RedirectResponse("/configuracion/emisor", status_code=303)

    # URL tipo: /static/uploads/logo_emisor.png  -> nombre: logo_emisor.png
    filename = Path(emisor.logo_path).name
    file_path = UPLOAD_DIR / filename

    try:
        if file_path.exists():
            file_path.unlink()
        else:
            # Para depurar si hace falta
            print("Logo no encontrado en:", file_path)
    except Exception as e:
        print(f"Error eliminando logo: {e}")

    emisor.logo_path = None
    session.commit()

    return RedirectResponse("/configuracion/emisor", status_code=303)

# =========================================================
# TEXTOS LEGALES
# =========================================================
@router.post("/textos")
def emisor_textos(
    texto_pie: str = Form(""),
    texto_exento: str = Form(""),
    texto_rectificativa: str = Form(""),
    session: Session = Depends(get_session),
):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    emisor.texto_pie = texto_pie.strip()
    emisor.texto_exento = texto_exento.strip()
    emisor.texto_rectificativa = texto_rectificativa.strip()

    session.commit()
    return RedirectResponse("/configuracion/emisor", status_code=303)


# =========================================================
# CERTIFICADO DIGITAL
# =========================================================
@router.post("/certificado")
async def emisor_upload_certificado(
    file: UploadFile = File(...),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    if not file or not file.filename:
        raise HTTPException(400, "No se ha enviado ningún archivo")

    filename = file.filename.lower()
    if not filename.endswith((".pfx", ".p12")):
        raise HTTPException(400, "El certificado debe ser .pfx o .p12")

    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    path = CERT_DIR / "certificado.pfx"
    with open(path, "wb") as f:
        f.write(await file.read())

    emisor.certificado_path = str(path)
    emisor.certificado_password = password
    session.commit()

    return RedirectResponse("/configuracion/emisor", status_code=303)


@router.get("/certificado/info", response_class=JSONResponse)
def certificado_info(session: Session = Depends(get_session)):
    emisor = session.get(Emisor, 1)

    if not emisor or not emisor.certificado_path:
        return {"ok": False, "mensaje": "No hay certificado configurado"}

    try:
        with open(emisor.certificado_path, "rb") as f:
            pfx_data = f.read()

        _, cert, _ = pkcs12.load_key_and_certificates(
            pfx_data,
            emisor.certificado_password.encode() if emisor.certificado_password else None,
        )
        now = datetime.now(timezone.utc)
        sujeto = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        emisor_cert = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        valid_to = getattr(cert, "not_valid_after_utc", cert.not_valid_after)
        dias_restantes = (valid_to - now).days

        return {
            "ok": True,
            "titular": sujeto,
            "emisor": emisor_cert,
            "valido_desde": cert.not_valid_before.strftime("%d/%m/%Y"),
            "valido_hasta": cert.not_valid_after.strftime("%d/%m/%Y"),
            "dias_restantes": dias_restantes,
        }

    except Exception as e:
        return {"ok": False, "mensaje": str(e)}


@router.post("/test-cert", response_class=JSONResponse)
async def test_certificado(
    file: UploadFile = File(...),
    password: str = Form(""),
):
    if not file.filename.lower().endswith((".pfx", ".p12")):
        return {"ok": False, "mensaje": "El certificado debe ser .pfx o .p12"}

    try:
        contenido = await file.read()

        _, cert, _ = pkcs12.load_key_and_certificates(
            contenido,
            password.encode() if password else None,
        )

        if not cert:
            return {"ok": False, "mensaje": "Certificado inválido"}

        dias = (cert.not_valid_after_utc - datetime.now(timezone.utc)).days

        return {
            "ok": True,
            "titular": cert.subject.rfc4514_string(),
            "emisor": cert.issuer.rfc4514_string(),
            "dias_restantes": dias,
        }

    except Exception as e:
        return {"ok": False, "mensaje": str(e)}


# =========================================================
# RUTA PDF
# =========================================================
@router.post("/ruta-pdf")
def guardar_ruta_pdf(
    ruta_pdf: str = Form(""),
    session: Session = Depends(get_session),
):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    emisor.ruta_pdf = ruta_pdf.strip()
    session.commit()

    return RedirectResponse("/configuracion/emisor?tab=pdf", status_code=303)


# =========================================================
# SELECCIONAR CARPETA (SOLO LOCAL)
# =========================================================
@router.get("/seleccionar-carpeta", response_class=JSONResponse)
def seleccionar_carpeta():
    env = os.environ.get("ENV", "development")

    # Si estamos en producción Render → no se permite seleccionar carpeta
    if env == "production":
        return {
            "ok": False,
            "mensaje": "Esta función solo está disponible en instalación local. En servidor debe configurarse manualmente la ruta."
        }

    # Si Tk no está disponible (ej. Linux sin entorno gráfico)
    if not TK_AVAILABLE:
        return {
            "ok": False,
            "mensaje": "Tu sistema local no soporta selector gráfico. Introduce la ruta manualmente."
        }

    # Si estamos en local y Tk funciona → abrir selector
    try:
        root = Tk()
        root.withdraw()
        carpeta = askdirectory()
        root.destroy()

        return {
            "ok": True,
            "carpeta": carpeta or ""
        }

    except Exception as e:
        return {
            "ok": False,
            "mensaje": f"No fue posible abrir el selector: {e}"
        }

# =========================================================
# NUMERACIÓN
# =========================================================
@router.post("/numeracion")
def guardar_numeracion(
    serie_facturacion: str = Form(...),
    numeracion_plantilla: str = Form(...),
    session: Session = Depends(get_session),
):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    year = date.today().year

    existe = session.exec(
        select(Factura)
        .where(Factura.estado == "VALIDADA")
        .where(Factura.fecha.between(date(year, 1, 1), date(year, 12, 31)))
    ).first()

    if existe:
        raise HTTPException(400, "Ya hay facturas validadas este año")

    if "{NUM" not in numeracion_plantilla:
        raise HTTPException(400, "La plantilla debe contener {NUM}")

    emisor.serie_facturacion = serie_facturacion.strip()
    emisor.numeracion_plantilla = numeracion_plantilla.strip()
    emisor.siguiente_numero = 1
    emisor.ultimo_anio_numerado = None

    session.commit()
    return RedirectResponse("/configuracion/emisor?tab=numeracion", status_code=303)


# =========================================================
# API SEGURA
# =========================================================
@router.get("/api", response_class=JSONResponse)
def emisor_api(session: Session = Depends(get_session)):
    emisor = session.get(Emisor, 1)
    if not emisor:
        raise HTTPException(404, "Emisor no encontrado")

    return {
        "nombre": emisor.nombre,
        "nif": emisor.nif,
        "email": emisor.email,
        "pais": emisor.pais,
    }

# =========================================================
# PIN DE SEGURIDAD
# =========================================================

@router.post("/seguridad")
async def guardar_seguridad(
    request: Request,
    session: Session = Depends(get_session)
):
    form = await request.form()

    pin = form.get("pin")
    timeout = form.get("timeout")

    emisor = session.exec(select(Emisor).where(Emisor.id == 1)).first()

    emisor.seguridad_pin = pin if pin else None

    try:
        emisor.seguridad_timeout_min = int(timeout) if timeout else 0
    except:
        emisor.seguridad_timeout_min = 0

    login_timeout = int(form.get("seguridad_login_timeout_min", 0))
    emisor.seguridad_login_timeout_min = login_timeout


    session.add(emisor)
    session.commit()

    return RedirectResponse(
        url="/configuracion/emisor",
        status_code=303
    )
