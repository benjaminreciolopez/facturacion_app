from fastapi import HTTPException, Request

def get_empresa_id(request: Request) -> int:
    session = request.session or {}
    print("🟡 get_empresa_id() EJECUTANDO")
    print("🟡 SESSION RAW:", session)

    empresa = session.get("empresa_id")
    print("🟡 empresa_id EN SESSION:", empresa, type(empresa))

    if empresa is not None:
        try:
            empresa_int = int(empresa)
            print("🟢 DEVUELVO EMPRESA:", empresa_int)
            return empresa_int
        except Exception as e:
            print("🔴 ERROR casteando empresa_id:", e)

    user = session.get("user")
    print("🟡 USER EN SESSION:", user)

    if user:
        empresa_user = user.get("empresa_id")
        print("🟡 empresa_id EN USER:", empresa_user, type(empresa_user))
        if empresa_user is not None:
            empresa_user = int(empresa_user)
            session["empresa_id"] = empresa_user
            print("🟢 RECUPERADO DESDE USER:", empresa_user)
            return empresa_user

    print("🔴 >>> ERROR FINAL: Empresa NO en sesión")
    raise HTTPException(401, "Empresa no seleccionada en sesión")
