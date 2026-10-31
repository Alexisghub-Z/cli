"""Niveles de permiso del asistente.

El nivel lo declara cada herramienta, pero la decisión de ejecutar la
toma el bucle del agente llamando a `evaluar()`. Así una herramienta mal
escrita no puede saltarse el control por olvido.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Nivel(str, Enum):
    """Nivel de permiso requerido por una herramienta."""

    LIBRE = "libre"
    CONFIRMACION = "confirmacion"
    BLOQUEADO = "bloqueado"


class Decision(str, Enum):
    """Resultado de evaluar una acción."""

    PERMITIR = "permitir"
    PREGUNTAR = "preguntar"
    DENEGAR = "denegar"


@dataclass(frozen=True)
class Veredicto:
    """Decisión sobre una acción, con el motivo en español."""

    decision: Decision
    motivo: str

    @property
    def permitida(self) -> bool:
        return self.decision is not Decision.DENEGAR


def evaluar(nivel: Nivel, *, motivo_bloqueo: str | None = None) -> Veredicto:
    """Traduce un nivel de permiso en una decisión concreta."""
    if nivel is Nivel.BLOQUEADO:
        return Veredicto(
            Decision.DENEGAR,
            motivo_bloqueo or "Esta acción está bloqueada por seguridad.",
        )
    if nivel is Nivel.CONFIRMACION:
        return Veredicto(Decision.PREGUNTAR, "Requiere tu confirmación.")
    return Veredicto(Decision.PERMITIR, "Acción de solo lectura.")
