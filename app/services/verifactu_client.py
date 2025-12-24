import httpx
from fastapi import HTTPException
from app.models.configuracion_sistema import ConfiguracionSistema


async def enviar_factura_a_verifactu(factura_data: dict, config: ConfiguracionSistema):
    """
    Envía la factura al servidor Veri*Factu (mock en TEST).
    """

    if not config.verifactu_activo or config.verifactu_modo == "OFF":
        return {
            "status": "SKIPPED",
            "motivo": "VeriFactu desactivado"
        }

    if not config.verifactu_url:
        raise HTTPException(500, "No existe URL configurada para VeriFactu.")

    url = f"{config.verifactu_url}/verifactu/enviar"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=factura_data)

        if resp.status_code != 200:
            return {
                "status": "ERROR",
                "code": resp.status_code,
                "respuesta": resp.text
            }

        return resp.json()

    except Exception as e:
        return {
            "status": "ERROR",
            "motivo": str(e)
        }
