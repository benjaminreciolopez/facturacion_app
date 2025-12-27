from fastapi import HTTPException, Request

def get_empresa_id(request: Request) -> int:
    session = request.session or {}
    print("🟡 get_empresa_id() EJECUTANDO")
    print("🟡 SESSION RAW:", session)

    # 1️⃣ Intentar leer empresa_id directo
    empresa = session.get("empresa_id")
    if empresa:
        try:
            empresa = int(empresa)
            print("🟢 EMPRESA DIRECTA:", empresa)
            return empresa
        except:
            pass

    # 2️⃣ Recuperar desde user si existe
    user = session.get("user")
    if user:
        empresa_user = user.get("empresa_id")
        if empresa_user:
            empresa_user = int(empresa_user)
            session["empresa_id"] = empresa_user
            print("🟢 EMPRESA RECUPERADA DESDE USER:", empresa_user)
            return empresa_user

    print("🔴 NO HAY EMPRESA EN SESIÓN")
    raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")
