from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import smtplib
from sqlmodel import Session
from datetime import datetime

from app.db.session import get_session
from app.core.templates import templates
from app.models.configuracion_sistema import ConfiguracionSistema
from typing import Optional

router = APIRouter(
    prefix="/configuracion",
    tags=["Configuración del sistema"]
)
# ============================================================
# VER CONFIGURACIÓN DEL SISTEMA
# ============================================================
@router.get("/sistema", response_class=HTMLResponse)
def ver_configuracion_sistema(
    request: Request,
    session: Session = Depends(get_session),
):
    config = session.get(ConfiguracionSistema, 1)

    if not config:
        raise HTTPException(
            status_code=500,
            detail="Configuración del sistema no inicializada."
        )

    return templates.TemplateResponse(
        "configuracion/sistema.html",
        {
            "request": request,
            "config": config,
        }
    )


@router.post("/sistema")
def guardar_configuracion_sistema(
    request: Request,
    session: Session = Depends(get_session),

    verifactu_modo: str = Form("OFF"),
    verifactu_url: str | None = Form(None),

    facturas_inmutables: bool = Form(False),
    prohibir_borrado_facturas: bool = Form(False),
    bloquear_fechas_pasadas: bool = Form(False),

    auditoria_activa: bool = Form(False),
    nivel_auditoria: str = Form("BASICA"),

    # =====================
    # SMTP
    # =====================
    smtp_enabled: Optional[str] = Form(None),
    smtp_host: Optional[str] = Form(None),
    smtp_port: Optional[str] = Form(None),
    smtp_user: Optional[str] = Form(None),
    smtp_password: Optional[str] = Form(None),
    smtp_from: Optional[str] = Form(None),
    smtp_tls: Optional[str] = Form(None),
    smtp_ssl: Optional[str] = Form(None),
):
    config = session.get(ConfiguracionSistema, 1)

    if not config:
        raise HTTPException(
            status_code=500,
            detail="Configuración del sistema no inicializada."
        )

    # =========================
    # VALIDACIONES
    # =========================
    modos_validos = {"OFF", "TEST", "PRODUCCION"}
    if verifactu_modo not in modos_validos:
        raise HTTPException(
            status_code=400,
            detail="Modo Veri*Factu no válido."
        )

    niveles_validos = {"BASICA", "COMPLETA"}
    if nivel_auditoria not in niveles_validos:
        raise HTTPException(
            status_code=400,
            detail="Nivel de auditoría no válido."
        )

    # =========================
    # VERIFACTU URL
    # =========================
    if verifactu_modo != "OFF":
        if not verifactu_url or verifactu_url.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="Debe especificar la URL del servidor Veri*Factu."
            )

        verifactu_url = verifactu_url.rstrip("/")

        if not (
            verifactu_url.startswith("http://")
            or verifactu_url.startswith("https://")
        ):
            raise HTTPException(
                status_code=400,
                detail="La URL Veri*Factu debe comenzar por http:// o https://"
            )

        config.verifactu_url = verifactu_url
        config.verifactu_activo = True
    else:
        config.verifactu_activo = False
        config.verifactu_url = None

    # =========================
    # CONFIG GENERAL
    # =========================
    config.verifactu_modo = verifactu_modo

    config.facturas_inmutables = facturas_inmutables
    config.prohibir_borrado_facturas = prohibir_borrado_facturas
    config.bloquear_fechas_pasadas = bloquear_fechas_pasadas

    config.auditoria_activa = auditoria_activa
    config.nivel_auditoria = nivel_auditoria

    config.actualizado_en = datetime.utcnow()

    # =========================
    # SMTP (EMAIL)
    # =========================
    config.smtp_enabled = smtp_enabled is not None
    config.smtp_host = smtp_host or None
    if smtp_port:
        config.smtp_port = int(smtp_port)
    else:
        config.smtp_port = 465 if smtp_ssl else 587
    config.smtp_user = smtp_user or None

    if smtp_password and smtp_password.strip() != "":
        config.smtp_password = smtp_password  # si cambias contraseña, se guarda

    config.smtp_from = smtp_from or smtp_user or None
    # No permitir TLS + SSL a la vez
    if smtp_tls and smtp_ssl:
        raise HTTPException(
            status_code=400,
            detail="No puedes activar TLS y SSL al mismo tiempo. Selecciona solo uno."
        )
    if config.smtp_port == 465:
        config.smtp_ssl = True
        config.smtp_tls = False

    if config.smtp_port == 587:
        config.smtp_tls = True
        config.smtp_ssl = False

    session.add(config)
    session.commit()

    return RedirectResponse(
        url="/configuracion/sistema",
        status_code=303
    )




def translate_smtp_error(e: Exception | str):
    msg = str(e)

    # ---------- TIMEOUT ----------
    if "timed out" in msg.lower():
        return {
            "title": "Tiempo de espera agotado",
            "msg": "El servidor SMTP no respondió.",
            "help": "Servidor incorrecto o puerto bloqueado por firewall."
        }

    # ---------- STARTTLS NECESARIO ----------
    if "STARTTLS" in msg or "530 5.7.0" in msg:
        return {
            "title": "El servidor requiere STARTTLS",
            "msg": "Debes activar TLS.",
            "help": "Usa puerto 587 con TLS activado y SSL desactivado."
        }

    # ---------- OUTLOOK ----------
    if "Authentication unsuccessful" in msg or "5.7.139" in msg or "535" in msg:
        return {
            "title": "Outlook / Microsoft requiere configuración extra",
            "msg": "Outlook ha bloqueado el acceso.",
            "help": (
                "Activa verificación en dos pasos y usa contraseña de aplicación.\n"
                "Puerto recomendado: 587 / TLS activado / SSL desactivado."
            ),
        }

    # ---------- GMAIL ----------
    if "Username and Password not accepted" in msg or "Application-specific password required" in msg:
        return {
            "title": "Google / Gmail ha rechazado el login",
            "msg": "Credenciales no válidas.",
            "help": "Debes usar contraseña de aplicación de Google, no la contraseña normal."
        }

    # ---------- TLS WRONG VERSION ----------
    if "WRONG_VERSION_NUMBER" in msg or "SSL" in msg:
        return {
            "title": "Error de seguridad (TLS/SSL incorrecto)",
            "msg": "TLS/SSL no coincide.",
            "help": "587 + TLS ó 465 + SSL."
        }

    # ---------- SERVIDOR NO ENCONTRADO ----------
    if "Name or service not known" in msg or "getaddrinfo failed" in msg:
        return {
            "title": "Servidor SMTP no encontrado",
            "msg": "El nombre del servidor es incorrecto.",
            "help": "Ejemplo: smtp.gmail.com, smtp.office365.com"
        }

    # ---------- CONEXIÓN RECHAZADA ----------
    if "Connection refused" in msg:
        return {
            "title": "No se puede conectar al servidor SMTP",
            "msg": "Conexión rechazada.",
            "help": "Servidor o puerto incorrecto."
        }

    # ---------- GENÉRICO ----------
    return {
        "title": "Error al conectar al correo",
        "msg": msg,
        "help": "Revise la configuración del servidor SMTP."
    }


@router.post("/sistema/test-smtp")
def test_smtp_manual(
    session: Session = Depends(get_session),

    smtp_host: str | None = Form(None),
    smtp_port: str | None = Form(None),
    smtp_user: str | None = Form(None),
    smtp_password: str | None = Form(None),
    smtp_tls: str | None = Form(None),
    smtp_ssl: str | None = Form(None),
):
    config = session.get(ConfiguracionSistema, 1)

    # Prioridad: formulario > BD > default
    host = smtp_host if smtp_host not in (None, "") else config.smtp_host
    port = int(smtp_port) if smtp_port not in (None, "") else (config.smtp_port or 587)

    if not host:
        return JSONResponse(
            {"ok": False, "msg": "Debe indicar el servidor SMTP."},
            status_code=400
        )

    use_tls = bool(smtp_tls) or bool(config.smtp_tls)
    use_ssl = bool(smtp_ssl) or bool(config.smtp_ssl)

    try:
        # Conexión
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                server.starttls()

        # EHLO obligatorio → si falla, aquí peta
        server.ehlo()

        # Login si hay credenciales → así probamos autenticación real
        user = smtp_user or config.smtp_user
        password = smtp_password or config.smtp_password

        if user and password:
            server.login(user, password)

        server.quit()

        return JSONResponse(
            {"ok": True, "msg": "Conexión SMTP correcta"},
            status_code=200
        )

    except Exception as e:
        return JSONResponse(
            {"ok": False, **translate_smtp_error(e)},
            status_code=400
        )
