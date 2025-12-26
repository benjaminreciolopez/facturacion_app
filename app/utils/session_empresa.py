from fastapi import Request, HTTPException

def get_empresa_id(request: Request):
    print("SESSION >>>", request.session)
    empresa_id = request.session.get("empresa_id")

    # Si ya existe → OK
    if empresa_id:
        return empresa_id

    # Intentar recuperar desde usuario en sesión
    user = request.session.get("user")
    if user and user.get("empresa_id"):
        empresa_id = user["empresa_id"]
        request.session["empresa_id"] = empresa_id
        return empresa_id

    raise HTTPException(401, "Sesión no iniciada o empresa no seleccionada")
