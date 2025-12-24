from sqlmodel import Session, create_engine
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}  # ← necesario en SQLite
)

def get_session():
    with Session(engine) as session:
        yield session
