from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request
from datetime import datetime, timedelta

from app.db.session import Session, engine
from app.models.emisor import Emisor
from app.models.user import User
from app.core.logger import logger


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        path = request.url.path
        logger.debug(f"[AUTH] PATH: {path}")


        session = request.session
        logger.debug(f"[AUTH] SESSION: {session}")

        # ---------------------------------------------------
        # RUTAS PÚBLICAS
        # ---------------------------------------------------
        rutas_publicas = (
            "/login",
            "/setup",
            "/logout",
            "/registro",
            "/pin",
            "/static",
            "/pdf",
            "/favicon.ico",
            "/offline",
            "/manifest.json",
            "/sw.js",

        )

        if any(path.startswith(r) for r in rutas_publicas):
            return await call_next(request)

        # ---------------------------------------------------
        # VALIDAR LOGIN (existencia de sesión)
        # ---------------------------------------------------
        user_session = session.get("user")

        if not user_session:
            logger.warning("Acceso sin sesión. Redirigiendo a login.")
            return RedirectResponse("/login", status_code=303)

        logger.debug(f"Usuario en sesión: {user_session}")

        # ------------------- VALIDACIÓN REAL EN BD -------------------
        with Session(engine) as db:
            real_user = db.get(User, user_session["id"])

        if not real_user:
            logger.error("Usuario en sesión NO existe en BD. Limpiando sesión.")
            session.clear()
            return RedirectResponse("/login", status_code=303)

        if not real_user.activo:
            logger.error("Usuario inactivo. Limpiando sesión.")
            session.clear()
            return RedirectResponse("/login", status_code=303)

        logger.debug(f"Usuario validado: {real_user.email}")
        logger.debug(f"EMPRESA USER REAL: {real_user.empresa_id}")

        # Sincronizar sesión si cambiaron datos
        session["user"] = {
            "id": real_user.id,
            "email": real_user.email,
            "empresa_id": real_user.empresa_id,
            "rol": real_user.rol
        }

        # ---- Empresa activa obligatoria ----
        empresa_id = real_user.empresa_id or 1
        session["empresa_id"] = empresa_id
        logger.debug(f"EMPRESA ACTIVA SESIÓN: {empresa_id}")
        # ---------------------------------------------------
        # CARGAR EMISOR
        # ---------------------------------------------------
        with Session(engine) as db:
            emisor = db.get(Emisor, 1)

        if not emisor:
            logger.info("No existe emisor. Continuando sin seguridad.")
            return await call_next(request)

        logger.debug(f"PIN: {emisor.seguridad_pin}")
        logger.debug(f"PIN timeout: {emisor.seguridad_timeout_min} min")
        logger.debug(f"LOGIN timeout: {emisor.seguridad_login_timeout_min} min")

        ahora = datetime.utcnow()

        # ===================================================
        #   LOGIN TIMEOUT (expira sesión por INACTIVIDAD)
        # ===================================================
        ultimo_login = session.get("ultimo_login")

        if emisor.seguridad_login_timeout_min and emisor.seguridad_login_timeout_min > 0:
            if not ultimo_login:
                session["ultimo_login"] = ahora.isoformat()
            else:
                ultimo_login_dt = datetime.fromisoformat(ultimo_login)
                limite_login = ultimo_login_dt + timedelta(
                    minutes=emisor.seguridad_login_timeout_min
                )

                logger.debug(f"Límite login (inactividad): {limite_login}")

                if ahora > limite_login:
                    logger.info("Login timeout por INACTIVIDAD → sesión cerrada")
                    session.clear()
                    return RedirectResponse("/login?expired=1", status_code=303)

            # IMPORTANTE:
            # Aquí sí refrescamos marca solo cuando hay actividad válida
            session["ultimo_login"] = ahora.isoformat()

        else:
            logger.debug("Login timeout desactivado")

        # ===================================================
        #   CONTROL DE PIN
        # ===================================================
        if not emisor.seguridad_pin or emisor.seguridad_timeout_min <= 0:
            logger.debug("Seguridad PIN desactivada.")
            return await call_next(request)

        ultimo = session.get("ultimo_acceso")
        pin_pendiente = session.get("pin_pendiente", False)

        logger.debug(f"Último acceso: {ultimo}")
        logger.debug(f"PIN pendiente: {pin_pendiente}")

        if pin_pendiente:
            logger.info("PIN requerido. Redirigiendo a /pin")
            return RedirectResponse("/pin", status_code=303)

        if not ultimo:
            session["ultimo_acceso"] = ahora.isoformat()
            logger.debug("Primer registro de actividad creado")
            return await call_next(request)

        ultimo_dt = datetime.fromisoformat(ultimo)
        limite = ultimo_dt + timedelta(minutes=emisor.seguridad_timeout_min)

        logger.debug(f"Límite PIN: {limite}")

        if ahora > limite:
            logger.info("PIN timeout → bloqueo activado")
            session["pin_pendiente"] = True
            session["ultimo_acceso"] = ahora.isoformat()
            return RedirectResponse("/pin", status_code=303)

        session["ultimo_acceso"] = ahora.isoformat()
        logger.debug("PIN OK. Continuando.")

        return await call_next(request)
