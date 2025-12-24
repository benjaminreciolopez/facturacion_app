from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime

from app.models.cliente import Cliente
from app.models.linea_factura import LineaFactura


class Factura(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(foreign_key="empresa.id")

    numero: Optional[str] = None
    fecha: date

    cliente_id: int = Field(foreign_key="cliente.id")
    cliente: Optional[Cliente] = Relationship(back_populates="facturas")

    # Totales
    subtotal: float = 0.0
    iva_global: float = 0.0        # <--- IVA global directamente (%)
    iva_total: float = 0.0
    total: float = 0.0

    mensaje_iva: Optional[str] = None
    rectificativa: bool = False
    ruta_pdf: Optional[str] = None

    estado: str = "BORRADOR"
    
    fecha_validacion: Optional[datetime] = None
    offline_id: str | None = Field(
    default=None,
    index=True,
    sa_column_kwargs={"nullable": True}
)

    lineas: List[LineaFactura] = Relationship(back_populates="factura")

    serie: Optional[str] = None
    verifactu_hash: str | None = Field(default=None)
    verifactu_fecha_generacion: Optional[datetime] = None
    registros_verifactu: List["RegistroVerifactu"] = Relationship(
        back_populates="factura"
    )

class RegistroVerifactu(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    factura_id: int = Field(foreign_key="factura.id")
    factura: Optional[Factura] = Relationship(back_populates="registros_verifactu")

    numero_factura: str
    fecha_factura: date
    total_factura: float

    hash_actual: str
    hash_anterior: Optional[str] = None

    fecha_registro: datetime = Field(default_factory=datetime.utcnow)

    estado_envio: str = Field(default="PENDIENTE")  # PENDIENTE | ENVIADO | ERROR
    error_envio: Optional[str] = None
