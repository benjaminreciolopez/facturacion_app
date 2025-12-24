A continuación tienes el README técnico y estratégico, listo para usar como documento base del proyecto. Está redactado para que puedas:

Pegarle directamente en el repositorio

Usarlo como contexto inicial en nuevos chats

Justificar decisiones técnicas y fiscales

Escalar el producto sin reescrituras

Sistema de Facturación Profesional (facturación_app)
1. Visión general

Este proyecto es un sistema de facturación profesional, diseñado desde el inicio para cumplir con la normativa fiscal española y preparado para los requisitos presentes y futuros de la AEAT, incluyendo Veri*Factu.

No es un prototipo ni un experimento: constituye una base sólida de aplicación productiva, pensada para integrarse como motor fiscal dentro de un ecosistema mayor (por ejemplo, app180), o funcionar de forma independiente.

2. Arquitectura técnica
Backend

FastAPI

SQLModel

Arquitectura modular (servicios, modelos, rutas)

Punto único de validación fiscal

Base de datos

Relacional

SQLite en desarrollo

Diseño preparado para migración a PostgreSQL

Modelo consistente y alineado con ORM

Generación de documentos

ReportLab

PDFs con estructura fiscal correcta

Preparado para:

QR Veri*Factu

Firma digital futura

Copias inmutables

3. Modelo fiscal y ciclo de vida de la factura

El sistema implementa un flujo de estados estricto, respetado tanto en backend como en frontend.

Estado	Significado	Acciones permitidas
BORRADOR	Editable, sin efectos fiscales	Editar, eliminar, validar
VALIDADA	Fiscalmente emitida	Ver PDF, anular
ANULADA	Sin efectos fiscales	Ver PDF
RECTIFICATIVA	Ajuste fiscal (factura derivada)	Ver PDF

Este modelo evita errores habituales en software de facturación amateur.

4. Validación fiscal

Antes de validar una factura, el sistema garantiza:

Orden cronológico de fechas

Existencia y permisos de escritura del PDF

Recalculo de importes desde líneas reales

Bloqueo definitivo de numeración

Una factura validada:

No puede editarse

No puede eliminarse

No puede alterarse sin trazabilidad

5. Anulación y rectificación

La anulación de una factura validada sigue el modelo fiscal correcto en España:

La factura original pasa a estado ANULADA

Se genera automáticamente una factura rectificativa

La rectificativa:

Mantiene numeración con sufijo R

Contiene líneas en negativo

Incluye texto legal conforme a la Ley del IVA

Genera su propio PDF

Queda en estado VALIDADA

No se trata de un cambio visual, sino de un ajuste fiscal real y trazable.

6. Veri*Factu (base preparada)

El sistema dispone de un punto único de control:

verificar_verifactu(...)


Este punto:

Centraliza validaciones

Genera hash encadenado

Registra auditoría (RegistroVerifactu)

Permite modos:

OFF

TEST

PRODUCCIÓN

La arquitectura es compatible con:

Certificado AEAT

Envío real a la Agencia Tributaria

Gestión de respuestas y errores

7. Auditoría y trazabilidad

Cada acción crítica queda registrada:

Entidad afectada (FACTURA)

Acción (VALIDAR, ANULAR, EDITAR…)

Resultado (OK / ERROR)

Motivo del fallo (si aplica)

Este nivel de trazabilidad es clave en software fiscal profesional.

8. Integración con app180

Este sistema está diseñado para integrarse con app180 como motor fiscal, manteniendo separación de responsabilidades.

Rol de cada sistema

app180: gestión operativa (tiempos, clientes, proyectos, actividad)

facturación_app: emisión fiscal, validación, auditoría, Veri*Factu

Modelo de integración recomendado

Integración por API / servicios

Compartir:

company_id

user_id

Autenticación centralizada

facturación_app no gestiona identidad, solo permisos

Este enfoque evita mezclar lógica fiscal con lógica operativa.

9. Estado actual del proyecto

Actualmente el sistema es:

Estable

Consistente

Alineado entre frontend y backend

Libre de incoherencias de modelo

Errores recientes corregidos:

Columnas fantasma en base de datos

Persistencia incorrecta de rutas PDF

Estados mal tratados

Acciones UI incoherentes

10. Trabajo pendiente (roadmap)
Prioridad alta

Introducir Alembic (migraciones)

Separar entornos dev / prod

Migrar a PostgreSQL en producción

Prioridad media

UX semántica (relación original ↔ rectificativa)

Badges claros por estado

Confirmaciones más explícitas

Prioridad futura

Envío real Veri*Factu

Gestión de respuestas AEAT

Firma digital del PDF

Exportación de libros IVA

Informes trimestrales

11. Conclusión

Este proyecto:

No es un juguete

Tiene un modelo fiscal correcto

Presenta una arquitectura escalable

Está preparado para normativa futura

Puede operar de forma independiente o integrada

El trabajo actual ya no es corregir errores, sino refinar, endurecer y cerrar funcionalidades