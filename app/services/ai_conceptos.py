# app/services/ai_conceptos.py
from __future__ import annotations

import re
from typing import Optional


def _limpiar_texto(txt: str) -> str:
    if not txt:
        return ""
    # Quitar espacios dobles y recortar
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def sugerir_nombre_concepto(descripcion: str) -> str:
    """
    Heurística sencilla para sugerir un nombre a partir de la descripción.
    Más adelante aquí puedes llamar a OpenAI si quieres algo más potente.
    """
    descripcion = _limpiar_texto(descripcion)
    if not descripcion:
        return ""

    # Tomamos las primeras 6 palabras
    palabras = descripcion.split(" ")
    base = " ".join(palabras[:6])

    # Quitar punto final si lo hay
    base = base.rstrip(".")

    # Capitalizar estilo título sencillo
    base = base[:1].upper() + base[1:]
    return base


def mejorar_descripcion_concepto(
    descripcion: str,
    nombre: Optional[str] = None,
) -> str:
    """
    Mejora ligera de descripción SIN IA externa:
    - Limpia espacios
    - Asegura mayúscula inicial
    - Añade punto final si no lo tiene

    Más adelante puedes reemplazar el cuerpo por una llamada a OpenAI.
    """
    desc = _limpiar_texto(descripcion)
    if not desc:
        return ""

    # Asegurar mayúscula inicial
    desc = desc[:1].upper() + desc[1:]

    # Añadir punto final si no lo tiene y si no termina en signo
    if desc[-1] not in ".!?":
        desc += "."

    return desc
