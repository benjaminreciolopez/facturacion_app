# app/services/resumen_fiscal_service.py

ESTADO_OK = "OK"
ESTADO_ADVERTENCIA = "ADVERTENCIA"
ESTADO_ERROR = "ERROR"


def calcular_estado_fiscal(
    ok: int,
    bloqueado: int,
    error: int,
) -> str:
    """
    Calcula el estado fiscal de una factura en base a auditoría.

    Prioridad:
    ERROR > ADVERTENCIA > OK
    """
    if error > 0:
        return ESTADO_ERROR

    if bloqueado > 0:
        return ESTADO_ADVERTENCIA

    return ESTADO_OK
