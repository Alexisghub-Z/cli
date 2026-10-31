"""Registro central de herramientas.

Agregar una herramienta nueva = decorarla con `@registrar`.
"""

from __future__ import annotations

from asistente.tools.base import Herramienta

_REGISTRO: dict[str, type[Herramienta]] = {}


def registrar(cls: type[Herramienta]) -> type[Herramienta]:
    """Decorador que añade una herramienta al registro."""
    for atributo in ("nombre", "descripcion", "Params"):
        if not getattr(cls, atributo, None):
            raise ValueError(f"{cls.__name__} no define '{atributo}'.")
    if cls.nombre in _REGISTRO:
        raise ValueError(f"Ya existe una herramienta llamada '{cls.nombre}'.")
    _REGISTRO[cls.nombre] = cls
    return cls


def obtener(nombre: str) -> type[Herramienta] | None:
    return _REGISTRO.get(nombre)


def todas() -> dict[str, type[Herramienta]]:
    return dict(_REGISTRO)


def esquemas() -> list[dict]:
    """Esquemas de todas las herramientas, para enviar al modelo."""
    return [cls.esquema_json() for cls in _REGISTRO.values()]
