from fastapi import Request, HTTPException

def get_empresa_id(request: Request) -> int:
    session = request.session or {}
    print("SESSION >>>", session)

    empresa = session.get("empresa_id")

    # Si ya existe y no es None
    if empresa is not None:
        try:
            return int(empresa)
        except:
            pass

    # Intentar recuperar del usuario autenticado
    user = session.get("user")
    if user:
        empresa_user = user.get("empresa_id")
        if empresa_user is not None:
            empresa_user = int(empresa_user)
            session["empresa_id"] = empresa_user
            print(">>> Recuperado empresa_id desde USER:", empresa_user)
            return empresa_user

    print(">>> ERROR: Empresa NO en sesión")
    raise HTTPException(401, "Empresa no seleccionada en sesión")
