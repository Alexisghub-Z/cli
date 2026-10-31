"""Modelo simulado: hace las pruebas independientes del modelo real."""

from __future__ import annotations

from typing import Any

from asistente.llm.base import (
    ClienteLLM,
    LlamadaHerramienta,
    RespuestaModelo,
)


class ClienteSimulado(ClienteLLM):
    """Devuelve respuestas predefinidas, en orden.

    Úsalo en pruebas: `ClienteSimulado([RespuestaModelo(...), ...])`.
    """

    def __init__(self, respuestas: list[RespuestaModelo] | None = None) -> None:
        self.respuestas = list(respuestas or [])
        self.recibidos: list[list[dict[str, Any]]] = []

    def responder(
        self,
        mensajes: list[dict[str, Any]],
        herramientas: list[dict[str, Any]] | None = None,
    ) -> RespuestaModelo:
        self.recibidos.append(list(mensajes))
        if not self.respuestas:
            return RespuestaModelo(texto="Listo.")
        return self.respuestas.pop(0)

    def disponible(self) -> tuple[bool, str]:
        return True, ""

    # Atajos para escribir pruebas más legibles.
    @staticmethod
    def con_herramienta(nombre: str, **argumentos: Any) -> RespuestaModelo:
        return RespuestaModelo(
            llamadas=[LlamadaHerramienta(nombre=nombre, argumentos=argumentos)]
        )

    @staticmethod
    def con_texto(texto: str) -> RespuestaModelo:
        return RespuestaModelo(texto=texto)
