"""Cliente de Ollama (API HTTP en localhost).

Tolera modelos pequeños que devuelven los argumentos como texto JSON
en lugar de objeto, o que envuelven la llamada en ```json ... ```.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from asistente.llm.base import (
    ClienteLLM,
    ErrorModelo,
    LlamadaHerramienta,
    RespuestaModelo,
)

_BLOQUE_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parsear_argumentos(crudo: Any) -> dict[str, Any]:
    """Normaliza los argumentos de una llamada a diccionario."""
    if isinstance(crudo, dict):
        return crudo
    if isinstance(crudo, str) and crudo.strip():
        try:
            valor = json.loads(crudo)
            return valor if isinstance(valor, dict) else {"valor": valor}
        except json.JSONDecodeError:
            return {}
    return {}


def extraer_llamada_del_texto(texto: str) -> LlamadaHerramienta | None:
    """Rescata una llamada que el modelo escribió como texto.

    Los modelos 3B-8B a veces ignoran el campo `tool_calls` y escriben
    el JSON en el cuerpo. Antes de reintentar, intentamos leerlo.
    """
    candidatos: list[str] = []
    for coincidencia in _BLOQUE_JSON.finditer(texto):
        candidatos.append(coincidencia.group(1))
    plano = texto.strip()
    if plano.startswith("{") and plano.endswith("}"):
        candidatos.append(plano)

    for candidato in candidatos:
        try:
            datos = json.loads(candidato)
        except json.JSONDecodeError:
            continue
        if not isinstance(datos, dict):
            continue
        nombre = datos.get("name") or datos.get("nombre") or datos.get("tool")
        if isinstance(nombre, str) and nombre:
            argumentos = (
                datos.get("arguments")
                or datos.get("argumentos")
                or datos.get("parameters")
                or {}
            )
            return LlamadaHerramienta(nombre, _parsear_argumentos(argumentos))
    return None


class ClienteOllama(ClienteLLM):
    """Habla con el servidor local de Ollama."""

    def __init__(
        self,
        modelo: str = "qwen3:8b",
        host: str = "http://localhost:11434",
        temperatura: float = 0.1,
        tiempo_limite: float = 120.0,
    ) -> None:
        self.modelo = modelo
        self.host = host.rstrip("/")
        self.temperatura = temperatura
        self.tiempo_limite = tiempo_limite

    def disponible(self) -> tuple[bool, str]:
        try:
            respuesta = httpx.get(f"{self.host}/api/tags", timeout=5.0)
            respuesta.raise_for_status()
        except httpx.ConnectError:
            return False, (
                "No encuentro Ollama en "
                f"{self.host}. ¿Está instalado y corriendo? "
                "Inícialo con: ollama serve"
            )
        except httpx.HTTPError as exc:
            return False, f"Ollama respondió con error: {exc}"

        etiquetas = respuesta.json().get("models", [])
        nombres = {m.get("name", "") for m in etiquetas}
        base = self.modelo.split(":")[0]
        if not any(n == self.modelo or n.startswith(base) for n in nombres):
            return False, (
                f"El modelo '{self.modelo}' no está descargado. "
                f"Descárgalo con: ollama pull {self.modelo}"
            )
        return True, ""

    def responder(
        self,
        mensajes: list[dict[str, Any]],
        herramientas: list[dict[str, Any]] | None = None,
    ) -> RespuestaModelo:
        cuerpo: dict[str, Any] = {
            "model": self.modelo,
            "messages": mensajes,
            "stream": False,
            "options": {"temperature": self.temperatura},
        }
        if herramientas:
            cuerpo["tools"] = herramientas

        try:
            respuesta = httpx.post(
                f"{self.host}/api/chat",
                json=cuerpo,
                timeout=self.tiempo_limite,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
        except httpx.ConnectError as exc:
            raise ErrorModelo(
                f"No pude conectar con Ollama en {self.host}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ErrorModelo(
                "El modelo tardó demasiado en responder. "
                "Prueba con un modelo más pequeño."
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ErrorModelo(f"Respuesta inválida de Ollama: {exc}") from exc

        mensaje = datos.get("message", {}) or {}
        texto = (mensaje.get("content") or "").strip()

        llamadas: list[LlamadaHerramienta] = []
        for cruda in mensaje.get("tool_calls") or []:
            funcion = cruda.get("function", {}) or {}
            nombre = funcion.get("name")
            if isinstance(nombre, str) and nombre:
                llamadas.append(
                    LlamadaHerramienta(
                        nombre, _parsear_argumentos(funcion.get("arguments"))
                    )
                )

        # Modelo pequeño que escribió la llamada en el texto.
        if not llamadas and texto:
            rescatada = extraer_llamada_del_texto(texto)
            if rescatada is not None:
                llamadas.append(rescatada)
                texto = ""

        return RespuestaModelo(texto=texto, llamadas=llamadas)
