"""Contrato que cumple toda herramienta del asistente."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from asistente.safety.permisos import Nivel


@dataclass
class Resultado:
    """Lo que devuelve una herramienta tras ejecutarse."""

    ok: bool
    resumen: str
    datos: dict[str, Any] = field(default_factory=dict)
    # Operaciones registradas para poder deshacer (las llena `undo/`).
    reversible: bool = False

    @classmethod
    def error(cls, mensaje: str) -> "Resultado":
        return cls(ok=False, resumen=mensaje)


class Herramienta(ABC):
    """Base de todas las herramientas.

    Las subclases declaran `nombre`, `descripcion`, `Params` y `nivel`.
    `run()` recibe parámetros ya validados por Pydantic; la comprobación
    de permisos y rutas la hace el agente antes de llamar aquí.
    """

    nombre: ClassVar[str]
    descripcion: ClassVar[str]
    nivel: ClassVar[Nivel] = Nivel.LIBRE
    Params: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, params: BaseModel) -> Resultado:
        """Ejecuta la herramienta con parámetros ya validados."""

    def rutas_afectadas(self, params: BaseModel) -> list[str]:
        """Rutas que esta llamada va a leer o modificar.

        El agente las revisa contra la lista de rutas protegidas.
        Por defecto toma los campos típicos de ruta.
        """
        rutas: list[str] = []
        for campo in ("ruta", "origen", "destino", "carpeta"):
            valor = getattr(params, campo, None)
            if isinstance(valor, str) and valor:
                rutas.append(valor)
        return rutas

    @classmethod
    def esquema_json(cls) -> dict[str, Any]:
        """Esquema en el formato de tool calling de Ollama/OpenAI."""
        esquema = cls.Params.model_json_schema()
        esquema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": cls.nombre,
                "description": cls.descripcion,
                "parameters": esquema,
            },
        }
