# app/models/password_reset.py

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select
import secrets


class PasswordReset(SQLModel, table=True):
    __tablename__ = "password_reset"

    id: Optional[int] = Field(default=None, primary_key=True)

    email: str = Field(index=True)
    token: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    used_at: Optional[datetime] = None
    is_used: bool = Field(default=False)

    ip_origen: Optional[str] = None
    tipo: str = Field(default="email")  # email | sistema futuro


    @property
    def is_expired(self):
        if not self.expires_at:
            return True

        now = datetime.now(timezone.utc)

        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        return now > exp

    @property
    def can_be_used(self) -> bool:
        return not self.is_used and not self.is_expired


# =========================
# HELPERS
# =========================

def create_password_reset(
    session: Session,
    email: str,
    hours_valid: int = 1,
) -> PasswordReset:
    """
    Crea y guarda un registro de reset de contraseña para un email.
    Sobrescribe/reset tokens antiguos del mismo email si quieres.
    """
    # Opcional: invalidar tokens antiguos del mismo email
    antiguos = session.exec(
        select(PasswordReset).where(
            PasswordReset.email == email,
            PasswordReset.is_used == False,  # noqa
        )
    ).all()
    for r in antiguos:
        r.is_used = True
        r.used_at = datetime.now(timezone.utc)
        session.add(r)

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    pr = PasswordReset(
        email=email,
        token=token,
        created_at=now,
        expires_at=now + timedelta(hours=hours_valid),
        is_used=False,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr


def get_password_reset_by_token(session: Session, token: str) -> Optional[PasswordReset]:
    return session.exec(
        select(PasswordReset).where(PasswordReset.token == token)
    ).first()


def mark_password_reset_used(session: Session, pr: PasswordReset) -> None:
    pr.is_used = True
    pr.used_at = datetime.now(timezone.utc)
    session.add(pr)
    session.commit()
