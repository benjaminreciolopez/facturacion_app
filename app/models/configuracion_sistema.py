from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class ConfiguracionSistema(SQLModel, table=True):
    __tablename__ = "configuracionsistema"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 🔥 CLAVE MULTIEMPRESA
    empresa_id: int = Field(
        index=True,
        unique=True,
        foreign_key="empresa.id"
    )

    # ==================================================
    # VERI*FACTU
    # ==================================================
    verifactu_activo: bool = False
    verifactu_modo: str = Field(default="OFF", max_length=20)
    verifactu_url: Optional[str] = None
    verifactu_ultimo_hash: Optional[str] = None
    verifactu_ultimo_envio: Optional[datetime] = None

    # ==================================================
    # CERTIFICADO AEAT
    # ==================================================
    cert_aeat_path: Optional[str] = None
    cert_aeat_password: Optional[str] = None
    cert_aeat_valido: bool = False
    cert_aeat_caduca_en: Optional[datetime] = None

    # ==================================================
    # CONTROL FACTURAS
    # ==================================================
    facturas_inmutables: bool = True
    prohibir_borrado_facturas: bool = True
    bloquear_fechas_pasadas: bool = False

    # ==================================================
    # AUDITORÍA
    # ==================================================
    auditoria_activa: bool = True
    nivel_auditoria: str = Field(default="BASICA", max_length=20)

    # ==================================================
    # SISTEMA
    # ==================================================
    pin_habilitado: bool = False

    creado_en: datetime = Field(default_factory=datetime.utcnow)
    actualizado_en: datetime = Field(default_factory=datetime.utcnow)

    # ==================================================
    # SMTP
    # ==================================================
    smtp_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: bool = True
    smtp_ssl: bool = False
