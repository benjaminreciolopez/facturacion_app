from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema de Facturación"
    API_V1_STR: str = "/api/v1"

    # ========================
    # DATABASE
    # ========================
    DATABASE_URL: str = "sqlite:////data/facturacion.db"

    # ========================
    # SECURITY / JWT
    # ========================
    SECRET_KEY: str = "dev-secret-key-cambia-esto"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ========================
    # PASSWORD
    # ========================
    PWD_SCHEME: str = "argon2"

    # ========================
    # APP MODE
    # ========================
    ENV: str = "development"

    # ========================
    # EMAIL
    # ========================
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_FROM: str = "no-reply@localhost"
    EMAIL_TLS: bool = True

    class Config:
        env_file = ".env.dev" if os.getenv("RENDER") is None else None


settings = Settings()
