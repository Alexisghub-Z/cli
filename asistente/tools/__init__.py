"""Herramientas del asistente.

`cargar_herramientas()` importa los módulos para que se registren.
"""

from __future__ import annotations


def cargar_herramientas() -> None:
    """Importa todas las herramientas para poblar el registro."""
    from asistente.tools import (  # noqa: F401
        archivos,
        buscar,
        comando,
        leer,
        listar,
        sistema,
    )
