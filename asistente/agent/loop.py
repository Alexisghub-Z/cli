"""Bucle del agente: pensar → elegir → validar → permiso → ejecutar → observar.

El modelo nunca ejecuta nada: solo propone llamadas a herramientas. Este
bucle las valida contra el esquema, consulta `safety/` y pide confirmación
antes de actuar.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from asistente.agent.prompt import prompt_sistema
from asistente.config import Config
from asistente.llm.base import ClienteLLM, ErrorModelo, LlamadaHerramienta
from asistente.safety import rutas as rutas_safety
from asistente.safety.permisos import Decision, Nivel, evaluar
from asistente.tools import registro
from asistente.tools.base import Resultado

# Devuelve True si el usuario autoriza la acción descrita.
Confirmador = Callable[[str, str], bool]


@dataclass
class Paso:
    """Un paso ejecutado del bucle, para mostrar y para las pruebas."""

    herramienta: str
    argumentos: dict[str, Any]
    resultado: Resultado


@dataclass
class Ejecucion:
    """Resultado completo de atender una petición."""

    respuesta: str = ""
    pasos: list[Paso] = field(default_factory=list)
    abortada: bool = False
    motivo_aborto: str = ""


def _firma(llamada: LlamadaHerramienta) -> str:
    """Identidad de una llamada, para detectar repeticiones."""
    return llamada.nombre + json.dumps(llamada.argumentos, sort_keys=True)


class Agente:
    """Orquesta modelo, herramientas y seguridad."""

    def __init__(
        self,
        cliente: ClienteLLM,
        config: Config | None = None,
        confirmador: Confirmador | None = None,
    ) -> None:
        self.cliente = cliente
        self.config = config or Config()
        # Sin confirmador explícito, se deniega lo que requiera permiso:
        # nunca asumimos un "sí" que el usuario no dio.
        self.confirmador = confirmador or (lambda nombre, detalle: False)

    def ejecutar(self, peticion: str) -> Ejecucion:
        """Atiende una petición en lenguaje natural."""
        mensajes: list[dict[str, Any]] = [
            {"role": "system", "content": prompt_sistema()},
            {"role": "user", "content": peticion},
        ]
        esquemas = registro.esquemas()
        ejecucion = Ejecucion()
        vistas: set[str] = set()
        errores_json = 0

        for _ in range(self.config.max_pasos):
            try:
                respuesta = self.cliente.responder(mensajes, esquemas)
            except ErrorModelo as exc:
                ejecucion.abortada = True
                ejecucion.motivo_aborto = str(exc)
                return ejecucion

            if not respuesta.quiere_herramienta:
                ejecucion.respuesta = respuesta.texto or "Listo."
                return ejecucion

            llamada = respuesta.llamadas[0]

            # Ciclo: el modelo repite exactamente la misma llamada.
            if _firma(llamada) in vistas:
                ejecucion.abortada = True
                ejecucion.motivo_aborto = (
                    f"El modelo repitió la misma acción ({llamada.nombre}) "
                    "sin avanzar. Me detengo para no entrar en un ciclo."
                )
                return ejecucion
            vistas.add(_firma(llamada))

            clase = registro.obtener(llamada.nombre)
            if clase is None:
                errores_json += 1
                if errores_json > 2:
                    ejecucion.abortada = True
                    ejecucion.motivo_aborto = (
                        "El modelo insistió en usar herramientas que no existen."
                    )
                    return ejecucion
                disponibles = ", ".join(registro.todas())
                mensajes.append(
                    {
                        "role": "user",
                        "content": (
                            f"La herramienta '{llamada.nombre}' no existe. "
                            f"Usa solo una de estas: {disponibles}."
                        ),
                    }
                )
                continue

            # Validación de parámetros con Pydantic; si falla, se reintenta
            # devolviendo el error al modelo (tu requisito del módulo llm).
            try:
                params = clase.Params(**llamada.argumentos)
            except ValidationError as exc:
                errores_json += 1
                if errores_json > 2:
                    ejecucion.abortada = True
                    ejecucion.motivo_aborto = (
                        f"No logré obtener parámetros válidos para "
                        f"'{llamada.nombre}'."
                    )
                    return ejecucion
                mensajes.append(
                    {
                        "role": "user",
                        "content": (
                            f"Los parámetros de '{llamada.nombre}' son "
                            f"inválidos: {exc.errors()}. Corrígelos."
                        ),
                    }
                )
                continue

            herramienta = clase()
            veredicto = self._autorizar(herramienta, params, clase.nivel)

            if veredicto.decision is Decision.DENEGAR:
                ejecucion.abortada = True
                ejecucion.motivo_aborto = veredicto.motivo
                return ejecucion

            if veredicto.decision is Decision.PREGUNTAR:
                detalle = ", ".join(
                    f"{k}={v}" for k, v in llamada.argumentos.items()
                )
                if not self.confirmador(llamada.nombre, detalle):
                    ejecucion.abortada = True
                    ejecucion.motivo_aborto = "Cancelado por ti."
                    return ejecucion

            resultado = herramienta.run(params)
            ejecucion.pasos.append(
                Paso(llamada.nombre, dict(llamada.argumentos), resultado)
            )

            mensajes.append(
                {
                    "role": "assistant",
                    "content": f"Usé {llamada.nombre}.",
                }
            )
            mensajes.append(
                {
                    "role": "user",
                    "content": (
                        f"Resultado de {llamada.nombre}: {resultado.resumen}\n"
                        f"Datos: {json.dumps(resultado.datos, ensure_ascii=False)[:1500]}\n"
                        "Si la tarea está completa, responde al usuario en "
                        "español sin usar más herramientas."
                    ),
                }
            )

        ejecucion.abortada = True
        ejecucion.motivo_aborto = (
            f"Alcancé el límite de {self.config.max_pasos} pasos."
        )
        return ejecucion

    def _autorizar(self, herramienta, params, nivel: Nivel):
        """Comprueba rutas protegidas y nivel de permiso."""
        if nivel is not Nivel.LIBRE:
            for ruta in herramienta.rutas_afectadas(params):
                protegida, motivo = rutas_safety.es_protegida(ruta)
                if protegida:
                    from asistente.safety.permisos import Veredicto

                    return Veredicto(
                        Decision.DENEGAR,
                        f"No puedo modificar «{ruta}»: {motivo}",
                    )
        return evaluar(nivel)
