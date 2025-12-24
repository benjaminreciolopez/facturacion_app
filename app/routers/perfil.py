from fastapi import APIRouter, Request, Depends
from app.core.templates import templates
from app.core.auth_utils import get_user_safe
from app.db.session import get_session
from sqlmodel import Session
from app.models.user import User

router = APIRouter()

@router.get("/perfil")
def perfil(request: Request, session: Session = Depends(get_session)):
    user = get_user_safe(request)

    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/login", status_code=303)

    # user es dict, no objeto -> usamos ["id"]
    db_user = session.get(User, user["id"])

    return templates.TemplateResponse(
        "perfil/perfil.html",
        {
            "request": request,
            "user": db_user,
        },
    )
