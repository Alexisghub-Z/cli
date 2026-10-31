"""Interfaz abstracta del cliente de modelo.

Permite cambiar de Ollama a llama.cpp u otro backend sin tocar el agente.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlamadaHerramienta:
    """Petición del modelo para usar una herramienta."""

    nombre: str
    argumentos: dict[str, Any] = field(default_factory=dict)


@dataclass
class RespuestaModelo:
    """Respuesta del modelo: texto y/o llamadas a herramientas."""

    texto: str = ""
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)

    @property
    def quiere_herramienta(self) -> bool:
        return bool(self.llamadas)


class ErrorModelo(RuntimeError):
    """Fallo al comunicarse con el modelo."""


class ClienteLLM(ABC):
    """Contrato mínimo de un backend de modelo."""

    @abstractmethod
    def responder(
        self,
        mensajes: list[dict[str, Any]],
        herramientas: list[dict[str, Any]] | None = None,
    ) -> RespuestaModelo:
        """Envía la conversación y devuelve la respuesta del modelo."""

    @abstractmethod
    def disponible(self) -> tuple[bool, str]:
        """`(True, "")` si el backend responde; si no, el motivo."""
