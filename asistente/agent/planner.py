"""Plan antes de actuar, para tareas de varios pasos.

En lugar de ejecutar herramientas una a una preguntando cada vez, el
modelo propone un plan completo; el usuario lo ve entero, con la vista
previa de los cambios, y lo aprueba una sola vez.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from asistente.llm.base import ClienteLLM, ErrorModelo
from asistente.tools import registro

_BLOQUE = re.compile(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", re.DOTALL)

_INSTRUCCION = """Analiza la petición del usuario y decide si necesita \
varios pasos.

Responde SOLO con un objeto JSON, sin texto alrededor:

{{"multipaso": true, "resumen": "qué vas a hacer, en una frase", \
"pasos": [{{"herramienta": "nombre", "argumentos": {{}}, \
"motivo": "para qué sirve este paso"}}]}}

Si se resuelve con una sola herramienta, responde:
{{"multipaso": false}}

Herramientas disponibles: {herramientas}

Reglas:
- Máximo 6 pasos.
- Usa solo las herramientas de la lista.
- No planifiques borrados permanentes: usa enviar_a_papelera.
- Si necesitas información antes de decidir (por ejemplo, listar una \
carpeta para saber qué hay), responde {{"multipaso": false}} y la pediremos \
paso a paso.

Petición: {peticion}"""


@dataclass
class PasoPlan:
    """Un paso propuesto, aún sin ejecutar."""

    herramienta: str
    argumentos: dict[str, Any] = field(default_factory=dict)
    motivo: str = ""


@dataclass
class Plan:
    """Plan propuesto por el modelo."""

    resumen: str = ""
    pasos: list[PasoPlan] = field(default_factory=list)

    @property
    def multipaso(self) -> bool:
        return len(self.pasos) > 1


def _extraer_json(texto: str) -> dict | None:
    """Saca el objeto JSON de la respuesta, tolerando markdown y ruido."""
    candidatos: list[str] = [m.group(1) for m in _BLOQUE.finditer(texto)]
    plano = texto.strip()
    if plano.startswith("{"):
        candidatos.append(plano)
    # Último recurso: el primer objeto equilibrado del texto.
    inicio = texto.find("{")
    if inicio >= 0:
        profundidad = 0
        for indice in range(inicio, len(texto)):
            if texto[indice] == "{":
                profundidad += 1
            elif texto[indice] == "}":
                profundidad -= 1
                if profundidad == 0:
                    candidatos.append(texto[inicio : indice + 1])
                    break

    for candidato in candidatos:
        try:
            datos = json.loads(candidato)
        except json.JSONDecodeError:
            continue
        if isinstance(datos, dict):
            return datos
    return None


def proponer(cliente: ClienteLLM, peticion: str, max_pasos: int = 6) -> Plan | None:
    """Pide un plan al modelo. `None` si no hace falta (una sola acción)."""
    disponibles = registro.todas()
    instruccion = _INSTRUCCION.format(
        herramientas=", ".join(sorted(disponibles)), peticion=peticion
    )

    try:
        respuesta = cliente.responder(
            [{"role": "user", "content": instruccion}], None
        )
    except ErrorModelo:
        # Sin plan, el agente sigue paso a paso: no es un fallo fatal.
        return None

    datos = _extraer_json(respuesta.texto or "")
    if not datos or not datos.get("multipaso"):
        return None

    pasos: list[PasoPlan] = []
    for crudo in datos.get("pasos") or []:
        if not isinstance(crudo, dict):
            continue
        nombre = crudo.get("herramienta") or crudo.get("tool") or ""
        if nombre not in disponibles:
            # Un paso inventado invalida el plan: mejor ir paso a paso.
            return None
        argumentos = crudo.get("argumentos") or crudo.get("arguments") or {}
        if not isinstance(argumentos, dict):
            argumentos = {}
        pasos.append(
            PasoPlan(
                herramienta=nombre,
                argumentos=argumentos,
                motivo=str(crudo.get("motivo") or ""),
            )
        )
        if len(pasos) >= max_pasos:
            break

    if len(pasos) < 2:
        return None

    return Plan(resumen=str(datos.get("resumen") or ""), pasos=pasos)
