from fastapi import HTTPException, Request

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

def get_empresa_id(request: Request) -> int:
    session = request.session or {}
    print("🟡 get_empresa_id() EJECUTANDO")
    print("🟡 SESSION RAW:", session)

    # 1️⃣ Empresa directa
    empresa = session.get("empresa_id")
    if empresa:
        try:
            empresa = int(empresa)
            print("🟢 EMPRESA DIRECTA:", empresa)
            return empresa
        except:
            pass

    # 2️⃣ Empresa desde user
    user = session.get("user")
    if user:
        empresa_user = user.get("empresa_id")
        if empresa_user:
            empresa_user = int(empresa_user)
            session["empresa_id"] = empresa_user
            print("🟢 EMPRESA RECUPERADA DESDE USER:", empresa_user)
            return empresa_user

    print("🔴 NO HAY EMPRESA EN SESIÓN")

    # =============================
    #   DIFERENCIAR API vs WEB
    # =============================
    path = request.url.path.lower()
    accept = (request.headers.get("accept") or "").lower()

    # 👉 SI ES API → JSON 401
    if path.startswith("/api") or "application/json" in accept:
        raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")

    # 👉 SI ES WEB / PWA → LOGIN
    return RedirectResponse("/login", status_code=303)
