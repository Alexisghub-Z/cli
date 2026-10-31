"""Configuración en TOML, en el directorio de configuración del usuario."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

_MODELO_POR_DEFECTO = "qwen3:8b"


def directorio_config() -> Path:
    """Directorio de configuración según el sistema operativo."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        raiz = Path(base) if base else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        raiz = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        raiz = Path(base) if base else Path.home() / ".config"
    return raiz / "asistente"


def directorio_datos() -> Path:
    """Directorio para respaldos, papelera y diario de operaciones."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        raiz = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        raiz = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        raiz = Path(base) if base else Path.home() / ".local" / "share"
    return raiz / "asistente"


@dataclass
class Config:
    """Opciones del asistente."""

    modelo: str = _MODELO_POR_DEFECTO
    host: str = "http://localhost:11434"
    temperatura: float = 0.1
    max_pasos: int = 8
    tiempo_limite: float = 120.0
    confirmar_siempre: bool = True

    @property
    def ruta_papelera(self) -> Path:
        return directorio_datos() / "papelera"

    @property
    def ruta_respaldos(self) -> Path:
        return directorio_datos() / "respaldos"

    @property
    def ruta_diario(self) -> Path:
        return directorio_datos() / "diario.jsonl"


def ruta_archivo_config() -> Path:
    return directorio_config() / "config.toml"


def cargar(ruta: Path | None = None) -> Config:
    """Lee la configuración; si no existe, devuelve los valores por defecto."""
    destino = ruta or ruta_archivo_config()
    if not destino.exists():
        return Config()
    try:
        with destino.open("rb") as archivo:
            datos = tomllib.load(archivo)
    except (OSError, tomllib.TOMLDecodeError):
        return Config()

    validos = {campo for campo in Config.__dataclass_fields__}
    filtrados = {k: v for k, v in datos.items() if k in validos}
    try:
        return Config(**filtrados)
    except TypeError:
        return Config()


def guardar(config: Config, ruta: Path | None = None) -> Path:
    """Escribe la configuración en TOML (sin dependencias extra)."""
    destino = ruta or ruta_archivo_config()
    destino.parent.mkdir(parents=True, exist_ok=True)

    lineas = ["# Configuración del asistente", ""]
    for clave, valor in asdict(config).items():
        if isinstance(valor, bool):
            lineas.append(f"{clave} = {str(valor).lower()}")
        elif isinstance(valor, (int, float)):
            lineas.append(f"{clave} = {valor}")
        else:
            escapado = str(valor).replace('"', '\\"')
            lineas.append(f'{clave} = "{escapado}"')
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return destino
