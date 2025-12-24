from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class ConfiguracionSistema(SQLModel, table=True):
    """
    Configuración global del sistema.
    Solo debe existir UNA fila (id = 1).
    Controla el comportamiento fiscal y normativo.
    """

    id: int = Field(default=1, primary_key=True)

    # ==================================================
    # VERI*FACTU
    # ==================================================

    verifactu_activo: bool = Field(default=False)

    # OFF | TEST | PRODUCCION
    verifactu_modo: str = Field(default="OFF", max_length=20)

    # URL del servicio de VERI*FACTU
    verifactu_url: Optional[str] = None   # ⬅️ NUEVO


    # Último hash encadenado (para VERI*FACTU)
    verifactu_ultimo_hash: Optional[str] = None

    # Fecha del último envío correcto
    verifactu_ultimo_envio: Optional[datetime] = None

    # ==================================================
    # CERTIFICADO AEAT (NO es el de firma PDF)
    # ==================================================

    cert_aeat_path: Optional[str] = None
    cert_aeat_password: Optional[str] = None

    cert_aeat_valido: bool = Field(default=False)
    cert_aeat_caduca_en: Optional[datetime] = None

    # ==================================================
    # CONTROL E INMUTABILIDAD
    # ==================================================

    # Si está activo, una factura VALIDADA no se puede modificar
    facturas_inmutables: bool = Field(default=True)

    # Si está activo, no se pueden borrar facturas validadas
    prohibir_borrado_facturas: bool = Field(default=True)

    # Si está activo, no se pueden cambiar fechas pasadas
    bloquear_fechas_pasadas: bool = Field(default=False)

    # ==================================================
    # AUDITORÍA
    # ==================================================

    auditoria_activa: bool = Field(default=True)

    # BASICA | COMPLETA
    nivel_auditoria: str = Field(default="BASICA", max_length=20)

    # ==================================================
    # SISTEMA
    # ==================================================
    pin_habilitado: bool = Field(default=False)

    creado_en: datetime = Field(default_factory=datetime.utcnow)
    actualizado_en: datetime = Field(default_factory=datetime.utcnow)

    smtp_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: bool = True
    smtp_ssl: bool = False
