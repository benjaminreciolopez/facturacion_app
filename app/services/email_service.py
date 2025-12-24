import os
import smtplib
import socket
import threading
import ssl

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from sqlmodel import Session
from app.db.session import engine
from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.emisor import Emisor
from app.services.facturas_pdf import generar_factura_pdf
from app.services.smtp_service import smtp_connect


# =========================
# CONFIG
# =========================
socket.setdefaulttimeout(10)   # timeout global duro


def _load_smtp_config():
    """
    Carga config SMTP desde BD
    """
    with Session(engine) as db:
        return db.get(ConfiguracionSistema, 1)


# =========================
# ENVÍO SIMPLE
# =========================
def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    cc: list[str] | None = None,
):
    cfg = _load_smtp_config()
    if not cfg or not cfg.smtp_enabled:
        raise RuntimeError("SMTP no está configurado")

    msg = MIMEMultipart("alternative")
    sender = cfg.smtp_from or cfg.smtp_user or "no-reply@example.com"

    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject

    cc_list = cc or []
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = [to_email] + cc_list

    server = smtp_connect(cfg)
    try:
        server.sendmail(sender, recipients, msg.as_string())
    finally:
        try:
            server.quit()
        except:
            pass


# =========================
# PASSWORD RESET
# =========================
def send_password_reset_email(to_email: str, reset_url: str):
    subject = "Recuperación de contraseña"

    text_body = f"""
Has solicitado restablecer la contraseña.

Enlace de recuperación:
{reset_url}

Si no solicitaste este cambio, ignora este correo.
"""

    html_body = f"""
<p>Has solicitado restablecer la contraseña.</p>
<p>Enlace de recuperación:</p>
<p>
  <a href="{reset_url}" target="_blank" rel="noopener noreferrer">
    Recuperar contraseña
  </a>
</p>
<p style="font-size: 12px; color: #666;">
  Si no solicitaste este cambio, ignora este correo.
</p>
"""

    send_email(to_email, subject, html_body, text_body)


# =========================
# ENVÍO FACTURA
# =========================
def enviar_email_factura(
    factura_id: int,
    para: str,
    asunto: str,
    cuerpo: str,
    cc=None,
    adjuntar_pdf=True,
):
    from app.models.factura import Factura

    # -------- Abrir sesión independiente --------
    with Session(engine) as session:
        factura = session.get(Factura, factura_id)
        if not factura:
            raise Exception("Factura no encontrada")

        session.refresh(factura)
        _ = factura.lineas

        config = session.get(ConfiguracionSistema, 1)
        emisor = session.get(Emisor, 1)

    if not config:
        raise Exception("No existe configuración del sistema")
    if not emisor:
        raise Exception("No existe configuración del emisor")

    # -------- Construcción email --------
    msg = MIMEMultipart()
    msg["From"] = config.smtp_user
    msg["To"] = para
    msg["Subject"] = asunto

    cc_list = []
    if cc:
        if isinstance(cc, str):
            cc_list = [c.strip() for c in cc.split(",") if c.strip()]
        elif isinstance(cc, list):
            cc_list = [c.strip() for c in cc if c.strip()]
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

    msg.attach(MIMEText(cuerpo, "html", "utf-8"))

    # -------- PDF --------
    if adjuntar_pdf:
        ruta_base = (emisor.ruta_pdf or "").strip()
        if not ruta_base:
            raise Exception("No hay ruta PDF configurada en Emisor")

        pdf_path = None

        if factura.ruta_pdf:
            year = factura.fecha.year
            trimestre = f"T{((factura.fecha.month - 1) // 3) + 1}"
            filename = os.path.basename(factura.ruta_pdf)
            pdf_path = os.path.join(ruta_base, str(year), trimestre, filename)

        if not pdf_path or not os.path.isfile(pdf_path):
            ruta_fisica, _ = generar_factura_pdf(
                factura=factura,
                lineas=factura.lineas,
                ruta_base=ruta_base,
                emisor=emisor,
                config=config
            )
            pdf_path = ruta_fisica

        if not os.path.isfile(pdf_path):
            raise Exception(f"No se encontró el PDF de la factura: {pdf_path}")

        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            filename = f"{factura.numero or 'FACTURA'}.pdf"
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

    # -------- SMTP --------
    server = smtp_connect(config)
    send_to = [para] + cc_list

    try:
        server.sendmail(config.smtp_user, send_to, msg.as_string())
    finally:
        try:
            server.quit()
        except:
            pass


# =========================
# BACKGROUND NO BLOQUEANTE
# =========================
def enviar_email_factura_background(
    factura_id: int,
    para: str,
    asunto: str,
    cuerpo: str,
    cc: list[str] | None,
    adjuntar_pdf: bool,
):
    enviar_email_factura(
        factura_id=factura_id,
        para=para,
        asunto=asunto,
        cuerpo=cuerpo,
        cc=cc,
        adjuntar_pdf=adjuntar_pdf,
    )


def run_async(fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


def enviar_email_factura_construido(
    smtp_config,
    para: str,
    asunto: str,
    cuerpo: str,
    cc: list[str] | None,
    pdf_path: str | None,
    remitente: str
):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    import ssl

    msg = MIMEMultipart()
    msg["From"] = remitente
    msg["To"] = para
    msg["Subject"] = asunto

    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(cuerpo, "html", "utf-8"))

    if pdf_path:
        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_path))
            msg.attach(part)

    context = ssl.create_default_context()

    if smtp_config["ssl"]:
        server = smtplib.SMTP_SSL(
            smtp_config["host"],
            smtp_config["port"],
            context=context,
            timeout=25
        )
    else:
        server = smtplib.SMTP(
            smtp_config["host"],
            smtp_config["port"],
            timeout=25
        )
        server.ehlo()
        if smtp_config["tls"]:
            server.starttls(context=context)

    if smtp_config["user"]:
        server.login(smtp_config["user"], smtp_config["password"])

    recipients = [para] + (cc or [])

    try:
        server.sendmail(remitente, recipients, msg.as_string())
    finally:
        try:
            server.quit()
        except:
            pass
