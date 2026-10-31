"""Reproduce una receta pasando por el sistema de permisos.

Una receta no es un atajo a la seguridad: cada paso se valida con
Pydantic, se comprueba contra las rutas protegidas y se muestra la vista
previa antes de pedir aprobación, igual que un plan propuesto por el
modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from asistente.agent.vista_previa import VistaPrevia, calcular
from asistente.recetas.modelo import Receta
from asistente.safety.permisos import Decision
from asistente.tools import cargar_herramientas, registro
from asistente.tools.base import Resultado


@dataclass
class PasoPreparado:
    """Un paso de la receta, ya validado y listo para ejecutar."""

    herramienta: str
    argumentos: dict[str, Any]
    instancia: Any
    params: Any
    vista: VistaPrevia | None = None


@dataclass
class ResultadoReceta:
    """Qué pasó al reproducir una receta."""

    pasos: list[tuple[str, Resultado]] = field(default_factory=list)
    abortada: bool = False
    motivo: str = ""

    @property
    def ok(self) -> bool:
        return not self.abortada and bool(self.pasos)


def preparar(
    receta: Receta,
    valores: dict[str, str],
    autorizar,
) -> tuple[list[PasoPreparado], str]:
    """Valida todos los pasos antes de ejecutar ninguno.

    `autorizar(herramienta, params, nivel)` es el comprobador de permisos
    del agente. Devuelve `(pasos, "")` o `([], motivo)`.
    """
    # Asegura el registro: sin esto, una herramienta existente parecería
    # borrada y el mensaje de error confundiría al usuario.
    cargar_herramientas()
    preparados: list[PasoPreparado] = []

    for numero, paso in enumerate(receta.pasos, start=1):
        clase = registro.obtener(paso.herramienta)
        if clase is None:
            return [], (
                f"El paso {numero} usa «{paso.herramienta}», que ya no existe. "
                "La receta se guardó con una versión anterior del asistente."
            )

        argumentos = paso.resolver(valores)
        # Un hueco sin rellenar llegaría literal («{carpeta}/PDF») y crearía
        # una carpeta con ese nombre: mejor detenerse.
        pendientes = paso.huecos() - set(valores)
        if pendientes:
            faltan = ", ".join(sorted(pendientes))
            return [], f"Falta indicar: {faltan}."

        try:
            params = clase.Params(**argumentos)
        except ValidationError as exc:
            primero = exc.errors()[0] if exc.errors() else {}
            campo = ".".join(str(p) for p in primero.get("loc", ())) or "?"
            return [], (
                f"El paso {numero} ({paso.herramienta}) tiene el parámetro "
                f"«{campo}» mal: {primero.get('msg', 'inválido')}."
            )

        instancia = clase()
        veredicto = autorizar(instancia, params, clase.nivel)
        if veredicto.decision is Decision.DENEGAR:
            return [], f"El paso {numero} está bloqueado: {veredicto.motivo}"

        preparados.append(
            PasoPreparado(
                herramienta=paso.herramienta,
                argumentos=argumentos,
                instancia=instancia,
                params=params,
                vista=calcular(paso.herramienta, params),
            )
        )

    return preparados, ""


def ejecutar(preparados: list[PasoPreparado]) -> ResultadoReceta:
    """Ejecuta los pasos ya preparados y aprobados."""
    resultado = ResultadoReceta()

    for paso in preparados:
        salida = paso.instancia.run(paso.params)
        resultado.pasos.append((paso.herramienta, salida))
        # Igual que en un plan: si un paso falla, los siguientes
        # probablemente dependían de él.
        if not salida.ok:
            resultado.abortada = True
            resultado.motivo = (
                f"El paso «{paso.herramienta}» falló: {salida.resumen} "
                "Detuve la receta aquí."
            )
            return resultado

    return resultado
