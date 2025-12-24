from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from sqlmodel import Session, select

from app.db.session import engine
from app.models.user import User


class FirstRunMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/static"):
            return await call_next(request)

        if request.url.path.startswith("/setup"):
            return await call_next(request)

        with Session(engine) as session:
            users = session.exec(select(User)).first()

            if not users:
                return RedirectResponse("/setup")

        return await call_next(request)
