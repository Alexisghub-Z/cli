"""Herramientas de información del sistema: disco y procesos."""

from __future__ import annotations

import shutil
import subprocess
import sys

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.listar import formato_tamano
from asistente.tools.registro import registrar


@registrar
class EspacioEnDisco(Herramienta):
    nombre = "espacio_en_disco"
    descripcion = (
        "Muestra el espacio total, usado y libre del disco. Úsala cuando el "
        "usuario pregunte cuánto espacio le queda."
    )
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        ruta: str = Field(
            default=".",
            description="Ruta del disco a consultar. Por defecto, el actual.",
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        destino = resolver(params.ruta)
        try:
            uso = shutil.disk_usage(destino)
        except OSError as exc:
            return Resultado.error(f"No pude consultar {destino}: {exc}")

        porcentaje = (uso.used / uso.total * 100) if uso.total else 0.0
        return Resultado(
            ok=True,
            resumen=(
                f"{formato_tamano(uso.free)} libres de "
                f"{formato_tamano(uso.total)} ({porcentaje:.0f}% usado)"
            ),
            datos={
                "ruta": str(destino),
                "total": uso.total,
                "usado": uso.used,
                "libre": uso.free,
                "total_legible": formato_tamano(uso.total),
                "usado_legible": formato_tamano(uso.used),
                "libre_legible": formato_tamano(uso.free),
                "porcentaje_usado": round(porcentaje, 1),
            },
        )


def _procesos_posix(limite: int) -> list[dict]:
    """Lee los procesos con `ps` (Linux y macOS)."""
    salida = subprocess.run(
        ["ps", "-eo", "pid,rss,pcpu,comm"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    filas: list[dict] = []
    for linea in salida.stdout.splitlines()[1:]:
        partes = linea.split(None, 3)
        if len(partes) < 4:
            continue
        try:
            filas.append(
                {
                    "pid": int(partes[0]),
                    "memoria_kb": int(partes[1]),
                    "cpu": float(partes[2]),
                    "nombre": partes[3].strip(),
                }
            )
        except ValueError:
            continue
    filas.sort(key=lambda f: f["memoria_kb"], reverse=True)
    return filas[:limite]


def _procesos_windows(limite: int) -> list[dict]:
    """Lee los procesos con `tasklist` (Windows)."""
    salida = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    filas: list[dict] = []
    for linea in salida.stdout.splitlines():
        campos = [c.strip('" ') for c in linea.split('","')]
        if len(campos) < 5:
            continue
        try:
            memoria = int(campos[4].replace(".", "").replace(",", "").split()[0])
            filas.append(
                {
                    "pid": int(campos[1]),
                    "memoria_kb": memoria,
                    "cpu": 0.0,
                    "nombre": campos[0],
                }
            )
        except (ValueError, IndexError):
            continue
    filas.sort(key=lambda f: f["memoria_kb"], reverse=True)
    return filas[:limite]


@registrar
class Procesos(Herramienta):
    nombre = "procesos"
    descripcion = (
        "Lista los procesos que más memoria consumen. Úsala cuando el "
        "usuario pregunte qué está lento o qué consume recursos."
    )
    # Solo lee información del sistema, así que no necesita confirmación.
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        limite: int = Field(
            default=10, ge=1, le=50, description="Cuántos procesos mostrar."
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        try:
            if sys.platform == "win32":
                filas = _procesos_windows(params.limite)
            else:
                filas = _procesos_posix(params.limite)
        except (OSError, subprocess.SubprocessError) as exc:
            return Resultado.error(f"No pude leer los procesos: {exc}")

        if not filas:
            return Resultado.error("No obtuve información de procesos.")

        for fila in filas:
            fila["memoria_legible"] = formato_tamano(fila["memoria_kb"] * 1024)

        principal = filas[0]
        return Resultado(
            ok=True,
            resumen=(
                f"{len(filas)} procesos; el que más consume es "
                f"{principal['nombre']} ({principal['memoria_legible']})"
            ),
            datos={"total": len(filas), "items": filas},
        )
