from sqlmodel import SQLModel

from app.models.emisor import Emisor
from app.models.cliente import Cliente
from app.models.factura import Factura
from app.models.linea_factura import LineaFactura
from app.models.iva import IVA
from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.auditoria import Auditoria
from app.models.empresa import Empresa
from app.models.user import User
from app.models.password_reset import PasswordReset
from app.models.envios_email import EnviosEmail
from app.models.concepto import Concepto



def init_db():
    from app.db.session import engine
    SQLModel.metadata.create_all(engine)
