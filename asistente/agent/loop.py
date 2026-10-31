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

from asistente.agent.planner import Plan, proponer
from asistente.agent.prompt import prompt_sistema
from asistente.agent.vista_previa import VistaPrevia, calcular
from asistente.config import Config
from asistente.llm.base import ClienteLLM, ErrorModelo, LlamadaHerramienta
from asistente.safety import rutas as rutas_safety
from asistente.safety.permisos import Decision, Nivel, evaluar
from asistente.tools import registro
from asistente.tools.base import Resultado

# Devuelve True si el usuario autoriza la acción.
# Recibe el nombre de la herramienta, el detalle y la vista previa
# (None cuando la acción no modifica nada previsible).
Confirmador = Callable[[str, str, "VistaPrevia | None"], bool]

# Muestra un plan completo y devuelve True si el usuario lo aprueba.
AprobadorPlan = Callable[["Plan", list[VistaPrevia | None]], bool]


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
    # Plan que se mostró al usuario, si la tarea fue de varios pasos.
    plan: "Plan | None" = None


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
        aprobador_plan: AprobadorPlan | None = None,
        planificar: bool = True,
    ) -> None:
        self.cliente = cliente
        self.config = config or Config()
        # Sin confirmador explícito, se deniega lo que requiera permiso:
        # nunca asumimos un "sí" que el usuario no dio.
        self.confirmador = confirmador or (
            lambda nombre, detalle, vista: False
        )
        # Sin aprobador, un plan no se puede autorizar en bloque y se cae
        # al modo paso a paso, que pregunta por cada acción.
        self.aprobador_plan = aprobador_plan
        self.planificar = planificar

    def ejecutar(self, peticion: str) -> Ejecucion:
        """Atiende una petición en lenguaje natural.

        Si la tarea necesita varios pasos, primero propone un plan con la
        vista previa de los cambios; aprobado en bloque, se ejecuta sin
        volver a preguntar por cada acción. Si no hay plan o el usuario no
        lo aprueba, se cae al modo paso a paso.
        """
        if self.planificar and self.aprobador_plan is not None:
            resultado_plan = self._intentar_plan(peticion)
            if resultado_plan is not None:
                return resultado_plan

        mensajes: list[dict[str, Any]] = [
            {"role": "system", "content": prompt_sistema()},
            {"role": "user", "content": peticion},
        ]
        esquemas = registro.esquemas()
        ejecucion = Ejecucion()
        vistas: set[str] = set()
        errores_json = 0
        # En el modo paso a paso cada acción se pregunta por separado.
        autorizado_por_plan = False

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

            if veredicto.decision is Decision.PREGUNTAR and not autorizado_por_plan:
                detalle = ", ".join(
                    f"{k}={v}" for k, v in llamada.argumentos.items()
                )
                vista = calcular(llamada.nombre, params)
                if not self.confirmador(llamada.nombre, detalle, vista):
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

    def _intentar_plan(self, peticion: str) -> Ejecucion | None:
        """Propone un plan y, si se aprueba, lo ejecuta.

        Devuelve `None` cuando no hay plan que valga (tarea de un paso,
        modelo que no responde, o plan rechazado), para que el llamador
        siga en modo paso a paso.
        """
        plan = proponer(self.cliente, peticion, max_pasos=self.config.max_pasos)
        if plan is None:
            return None

        # Valida todos los pasos ANTES de mostrar nada: un plan con un paso
        # inválido o bloqueado no se le presenta al usuario como viable.
        preparados: list[tuple[Any, Any, VistaPrevia | None]] = []
        for paso in plan.pasos:
            clase = registro.obtener(paso.herramienta)
            if clase is None:
                return None
            try:
                params = clase.Params(**paso.argumentos)
            except ValidationError:
                return None
            herramienta = clase()
            veredicto = self._autorizar(herramienta, params, clase.nivel)
            if veredicto.decision is Decision.DENEGAR:
                ejecucion = Ejecucion(plan=plan)
                ejecucion.abortada = True
                ejecucion.motivo_aborto = veredicto.motivo
                return ejecucion
            preparados.append(
                (herramienta, params, calcular(paso.herramienta, params))
            )

        vistas_previas = [vista for _, _, vista in preparados]
        if not self.aprobador_plan(plan, vistas_previas):
            ejecucion = Ejecucion(plan=plan)
            ejecucion.abortada = True
            ejecucion.motivo_aborto = "No aprobaste el plan."
            return ejecucion

        # Aprobado en bloque: se ejecuta sin preguntar paso a paso.
        ejecucion = Ejecucion(plan=plan)
        for (herramienta, params, _), paso in zip(preparados, plan.pasos):
            resultado = herramienta.run(params)
            ejecucion.pasos.append(
                Paso(paso.herramienta, dict(paso.argumentos), resultado)
            )
            # Un fallo detiene el plan: los pasos siguientes probablemente
            # dependían de este.
            if not resultado.ok:
                ejecucion.abortada = True
                ejecucion.motivo_aborto = (
                    f"El paso «{paso.herramienta}» falló: {resultado.resumen}. "
                    "Detuve el plan aquí."
                )
                return ejecucion

        hechos = len(ejecucion.pasos)
        ejecucion.respuesta = (
            plan.resumen or f"Completé el plan ({hechos} pasos)."
        )
        return ejecucion
