from fastapi import Request, HTTPException


def get_empresa_id(request: Request):
    print("SESSION >>>", request.session)

    # =========================
    # 1) SI EXISTE EN SESIÓN → OK
    # =========================
    if "empresa_id" in request.session and request.session["empresa_id"] is not None:
        return request.session["empresa_id"]

    # =========================
    # 2) INTENTAR RECUPERAR DESDE USER
    # =========================
    user = request.session.get("user")
    if user:
        empresa_id = user.get("empresa_id")

        if empresa_id:
            # Guardar en sesión para futuras peticiones
            request.session["empresa_id"] = empresa_id
            return empresa_id

    # =========================
    # 3) NO HAY EMPRESA → ERROR CONTROLADO
    # =========================
    raise HTTPException(
        status_code=401,
        detail="Empresa no seleccionada en sesión"
    )
