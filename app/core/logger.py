import logging

logger = logging.getLogger("factura")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
fmt = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(fmt)

logger.addHandler(handler)
