import smtplib
import ssl



def smtp_connect(config):
    user = config.smtp_user
    password = config.smtp_password

    try:
        TIMEOUT = 30

        # =========================
        # SSL DIRECTO (PUERTO 465)
        # =========================
        if config.smtp_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                config.smtp_host,
                config.smtp_port,
                context=context,
                timeout=TIMEOUT
            )

            # asegurar timeout en socket
            try:
                server.sock.settimeout(TIMEOUT)
            except:
                pass

            if user:
                server.login(user, password)

            return server

        # =========================
        # STARTTLS
        # =========================
        server = smtplib.SMTP(
            config.smtp_host,
            config.smtp_port,
            timeout=TIMEOUT
        )

        server.ehlo()

        if config.smtp_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()

        # asegurar timeout tras TLS
        try:
            server.sock.settimeout(TIMEOUT)
        except:
            pass

        if user:
            server.login(user, password)

        return server

    except Exception as e:
        raise RuntimeError(f"Error configurando conexión SMTP: {e}")