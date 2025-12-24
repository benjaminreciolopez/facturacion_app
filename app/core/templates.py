from fastapi.templating import Jinja2Templates
import json
from sqlmodel import SQLModel
from sqlmodel import Session
from app.db.session import engine
from app.models.emisor import Emisor
from app.core.auth_utils import get_user_safe


templates = Jinja2Templates(directory="app/templates")

# --- Filtro JSON seguro
def c_json(value):
    if isinstance(value, SQLModel):
        value = value.dict()
    return json.dumps(value, ensure_ascii=False, default=str)

templates.env.filters["c_json"] = c_json


# --- Global get_user
templates.env.globals["get_user"] = get_user_safe


# --- Logo del emisor
def get_emisor_logo():
    with Session(engine) as session:
        emisor = session.get(Emisor, 1)
        if not emisor or not emisor.logo_path:
            return None

        path = emisor.logo_path.strip()

        # Si ya comienza por /static → devolver tal cual
        if path.startswith("/static/"):
            return path

        # Si empieza por static sin barra
        if path.startswith("static/"):
            return "/" + path

        # Si solo guarda uploads/logo.png
        if path.startswith("uploads/"):
            return f"/static/{path}"

        # Si solo guarda el nombre del archivo
        return f"/static/uploads/{path}"
    
templates.env.globals["get_emisor_logo"] = get_emisor_logo