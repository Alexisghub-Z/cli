"""Lógica del modo interactivo, separada de la presentación para probarla.

- Interpreta lo que escribe el usuario: comandos fáciles, números de
  ejemplo, entradas vacías o sin sentido.
- Envuelve al cliente del modelo para anunciar las herramientas de solo
  lectura en cuanto el modelo las elige («🔍 Buscando en Descargas...»).
- Guarda los fallos internos en un log en lugar de enseñar tracebacks.
"""

from __future__ import annotations

import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from asistente import config as config_mod

_VOCALES = set("aeiouáéíóúü")
_CONSONANTES_SEGUIDAS = re.compile(r"[bcdfghjklmnñpqrstvwxyz]{5,}")

_COMANDOS = {
    "ayuda": "ayuda", "help": "ayuda", "?": "ayuda",
    "deshacer": "deshacer", "undo": "deshacer",
    "limpiar": "limpiar", "clear": "limpiar", "cls": "limpiar",
    "salir": "salir", "exit": "salir", "quit": "salir", "adios": "salir",
    "adiós": "salir", "chao": "salir",
}


def parece_sin_sentido(texto: str) -> bool:
    """Detecta entradas que no vale la pena mandar al modelo.

    Es conservador a propósito: solo atrapa lo claramente vacío o tecleado
    al azar («asdfgh», «jjjj», «???»), nunca una petición corta pero real.
    """
    letras = [c for c in texto.lower() if c.isalpha()]
    if len(letras) < 3:
        return True
    if not any(c in _VOCALES for c in letras):
        return True
    if len(set(letras)) <= 2:
        return True
    # Palabra por palabra: «los PDF» junta consonantes entre palabras.
    palabras = re.findall(r"[^\W\d_]+", texto.lower())
    return all(_CONSONANTES_SEGUIDAS.search(p) for p in palabras if len(p) > 4) and any(
        len(p) > 4 for p in palabras
    )


def resolver_entrada(texto: str, ejemplos: tuple[str, ...]) -> tuple[str, str]:
    """Clasifica lo que escribió el usuario.

    Devuelve `(tipo, valor)` con tipo en: comando, peticion, sugerir.
    """
    limpio = texto.strip()
    clave = limpio.lower().strip(".!¡ ")
    if clave in _COMANDOS:
        return "comando", _COMANDOS[clave]
    if clave.isdigit():
        indice = int(clave)
        if 1 <= indice <= len(ejemplos):
            return "peticion", ejemplos[indice - 1]
        return "sugerir", limpio
    if not limpio or parece_sin_sentido(limpio):
        return "sugerir", limpio
    return "peticion", limpio


def estado_ollama(cliente) -> str:
    """conectado, sin_modelo o sin_conexion (nunca lanza excepciones)."""
    try:
        ok, motivo = cliente.disponible()
    except Exception:  # noqa: BLE001 - cualquier fallo es «sin conexión»
        return "sin_conexion"
    if ok:
        return "conectado"
    if "no está descargado" in motivo:
        return "sin_modelo"
    return "sin_conexion"


def ruta_log() -> Path:
    return config_mod.directorio_datos() / "errores.log"


def registrar_error(exc: BaseException) -> Path | None:
    """Anota el traceback en el log de la app. Devuelve dónde quedó."""
    destino = ruta_log()
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("a", encoding="utf-8") as archivo:
            archivo.write(f"\n--- {datetime.now().isoformat(timespec='seconds')}\n")
            archivo.write(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            )
    except OSError:
        return None
    return destino


class ClienteVisible:
    """Envuelve al cliente del modelo para avisar qué herramienta eligió.

    Solo anuncia las herramientas de nivel LIBRE: esas se ejecutan en
    cuanto el modelo las pide. Las que necesitan permiso ya se muestran
    en la pantalla de confirmación, y anunciarlas antes confundiría.
    """

    def __init__(self, cliente, al_elegir: Callable[[str, dict], None]) -> None:
        self._cliente = cliente
        self._al_elegir = al_elegir

    def responder(self, mensajes: list[dict[str, Any]], herramientas=None):
        respuesta = self._cliente.responder(mensajes, herramientas)
        if getattr(respuesta, "quiere_herramienta", False):
            llamada = respuesta.llamadas[0]
            if _es_libre(llamada.nombre):
                self._al_elegir(llamada.nombre, dict(llamada.argumentos))
        return respuesta

    def __getattr__(self, nombre: str):
        return getattr(self._cliente, nombre)


def _es_libre(nombre: str) -> bool:
    from asistente.safety.permisos import Nivel
    from asistente.tools import registro

    clase = registro.obtener(nombre)
    return clase is not None and clase.nivel is Nivel.LIBRE
