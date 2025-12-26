from sqlmodel import SQLModel, Field
from typing import Optional


class Emisor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(foreign_key="empresa.id")

    # IDENTIFICACIÓN
    nombre: str = ""
    nif: str = ""

    # DIRECCIÓN FISCAL
    direccion: str = ""
    poblacion: str = ""
    provincia: str = ""
    cp: str = ""
    pais: str = "España"

    # CONTACTO
    telefono: str = ""
    email: str = ""
    web: Optional[str] = None

    # LOGO
    logo_path: Optional[str] = None

    # TEXTOS LEGALES
    texto_pie: Optional[str] = None
    texto_exento: Optional[str] = None
    texto_rectificativa: Optional[str] = None

    # CERTIFICADO DIGITAL
    firmar_pdf: bool = False
    certificado_path: Optional[str] = None
    certificado_password: Optional[str] = None

    # ============================
    # NUMERACIÓN
    # ============================

    # Tipo de numeración
    # BASICO → "2025-0001"
    # SERIE  → "A-2025-0001"
    modo_numeracion: str = Field(default="BASICO")

    # Serie para modo SERIE
    serie: Optional[str] = Field(default=None, max_length=10)

    # Serie predeterminada
    serie_facturacion: str = "A"

    # Plantilla
    numeracion_plantilla: str = "{SERIE}-{YEAR}-{NUM:04d}"

    # Control secuencial interno
    siguiente_numero: int = 1
    ultimo_anio_numerado: Optional[int] = None

    # Bloqueo
    numeracion_bloqueada: bool = Field(default=False)
    anio_numeracion_bloqueada: Optional[int] = None

    # Rutas
    ruta_pdf: Optional[str] = None
    ruta_facturas: Optional[str] = None

    # IVA
    mensaje_iva: Optional[str] = None

    # SEGURIDAD
    seguridad_pin: Optional[str] = None
    seguridad_timeout_min: int = 0
    auto_update: bool = False
    seguridad_login_timeout_min: int | None = 0

