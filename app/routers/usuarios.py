from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from datetime import datetime
from app.db.session import get_session
from app.models.user import User
from app.core.templates import templates
from app.core.security import get_password_hash


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


# ============================================================
# SOLO ADMIN
# ============================================================
def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user.get("rol") != "admin":
        raise HTTPException(403, "No autorizado")
    return user


# ============================================================
# LISTADO DE USUARIOS
# ============================================================
@router.get("")
def usuarios_list(
    request: Request,
    session: Session = Depends(get_session),
):
    user_session = require_admin(request)

    usuarios = session.exec(
        select(User)
        .where(User.empresa_id == user_session["empresa_id"])
        .where(User.activo == True)          # <<< SOLO usuarios activos
    ).all()

    return templates.TemplateResponse(
        "usuarios/list.html",
        {
            "request": request,
            "usuarios": usuarios,
        },
    )


# ============================================================
# CREAR USUARIO
# ============================================================
@router.post("/crear")
def usuarios_create(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form("user"),
    session: Session = Depends(get_session),
):
    user_session = require_admin(request)
    empresa_id = user_session["empresa_id"]

    # ───── Validar email duplicado globalmente ─────
    existe = session.exec(
        select(User).where(User.email == email.strip())
    ).first()

    if existe:
        return RedirectResponse("/usuarios?error=email", status_code=303)

    # ───── Crear usuario ─────
    user = User(
        email=email.strip(),
        password_hash=get_password_hash(password),
        rol=rol,
        activo=True,
        empresa_id=empresa_id,
    )

    session.add(user)
    session.commit()

    return RedirectResponse("/usuarios?ok=1", status_code=303)


# ============================================================
# ACTIVAR / DESACTIVAR USUARIO
# ============================================================
@router.get("/{user_id}/toggle")
def usuario_toggle(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user_session = require_admin(request)
    empresa_id = user_session["empresa_id"]

    user = session.get(User, user_id)

    # ───── Validaciones ─────
    if not user:
        return RedirectResponse("/usuarios?error=notfound", status_code=303)

    if user.empresa_id != empresa_id:
        return RedirectResponse("/usuarios?error=forbidden", status_code=303)

    # Evitar que un admin se desactive a sí mismo
    if user.id == user_session["id"]:
        return RedirectResponse("/usuarios?error=self", status_code=303)

    # ───── Alternar estado ─────
    user.activo = not user.activo
    session.commit()

    return RedirectResponse("/usuarios", status_code=303)

@router.post("/{user_id}/delete")
def eliminar_usuario(
    request: Request,
    user_id: int,
    session: Session = Depends(get_session)
):
    empresa_id = request.session.get("empresa_id")
    if not empresa_id:
        raise HTTPException(401, "Sesión no iniciada")

    user = session.get(User, user_id)

    if not user or user.empresa_id != empresa_id:
        raise HTTPException(404, "Usuario no encontrado")

    # No permitir borrar al último admin
    admins = session.exec(
        select(User).where(
            User.empresa_id == empresa_id,
            User.rol == "admin",
            User.activo == True
        )
    ).all()

    if user.rol == "admin" and len(admins) <= 1:
        raise HTTPException(400, "No puedes eliminar el único administrador del sistema")

    # Solo desactivar (soft delete simple)
    user.activo = False

    session.add(user)
    session.commit()

    return {"ok": True}

# ============================================================