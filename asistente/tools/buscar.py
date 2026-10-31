"""Herramienta: buscar archivos por nombre, extensión, tamaño o fecha."""

from __future__ import annotations

import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.listar import formato_tamano
from asistente.tools.registro import registrar

_LIMITE = 500
# Carpetas que nunca vale la pena recorrer: ruido y lentitud.
_IGNORADAS = frozenset(
    {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        ".mypy_cache", ".pytest_cache", "site-packages", ".cache",
        ".tox", "dist", "build", ".next", "target",
    }
)


@registrar
class BuscarArchivos(Herramienta):
    nombre = "buscar_archivos"
    descripcion = (
        "Busca archivos dentro de una carpeta y sus subcarpetas, filtrando "
        "por nombre, extensión, tamaño mínimo o antigüedad. Úsala cuando el "
        "usuario pregunte dónde está algo o qué archivos cumplen una condición."
    )
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        ruta: str = Field(
            default=".", description="Carpeta donde buscar, por ejemplo '~/Documentos'."
        )
        nombre: str = Field(
            default="",
            description="Texto que debe contener el nombre. Vacío = cualquiera.",
        )
        extension: str = Field(
            default="",
            description="Extensión sin punto, por ejemplo 'pdf'. Vacío = cualquiera.",
        )
        tamano_minimo_mb: float = Field(
            default=0.0, ge=0, description="Solo archivos de al menos estos MB."
        )
        dias_sin_modificar: int = Field(
            default=0,
            ge=0,
            description="Solo archivos sin modificar desde hace estos días.",
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        raiz = resolver(params.ruta)
        if not raiz.is_dir():
            return Resultado.error(f"No es una carpeta: {raiz}")

        texto = params.nombre.lower()
        extension = params.extension.lower().lstrip(".")
        minimo = int(params.tamano_minimo_mb * 1024 * 1024)
        corte = (
            time.time() - params.dias_sin_modificar * 86400
            if params.dias_sin_modificar
            else None
        )

        encontrados: list[dict] = []
        truncado = False
        # os.walk en lugar de Path.walk: este último requiere Python 3.12
        # y el proyecto admite 3.11.
        for actual_str, carpetas, archivos in os.walk(raiz, onerror=None):
            actual = Path(actual_str)
            # Poda in situ: evita entrar en carpetas de ruido.
            carpetas[:] = [
                c for c in carpetas if c not in _IGNORADAS and not c.startswith(".")
            ]
            for nombre_archivo in archivos:
                if texto and texto not in nombre_archivo.lower():
                    continue
                if extension and not nombre_archivo.lower().endswith(f".{extension}"):
                    continue
                ruta_archivo = actual / nombre_archivo
                try:
                    datos = ruta_archivo.stat()
                except OSError:
                    continue
                if minimo and datos.st_size < minimo:
                    continue
                if corte is not None and datos.st_mtime > corte:
                    continue

                encontrados.append(
                    {
                        "ruta": str(ruta_archivo),
                        "nombre": nombre_archivo,
                        "tamano": datos.st_size,
                        "tamano_legible": formato_tamano(datos.st_size),
                        "dias": int((time.time() - datos.st_mtime) / 86400),
                    }
                )
                if len(encontrados) >= _LIMITE:
                    truncado = True
                    break
            if truncado:
                break

        encontrados.sort(key=lambda item: item["tamano"], reverse=True)
        total_bytes = sum(item["tamano"] for item in encontrados)

        if not encontrados:
            return Resultado(
                ok=True,
                resumen=f"No encontré archivos que cumplan la condición en {raiz}",
                datos={"ruta": str(raiz), "total": 0, "items": []},
            )

        resumen = (
            f"{len(encontrados)} archivos en {raiz} "
            f"({formato_tamano(total_bytes)} en total)"
        )
        if truncado:
            resumen += f"; me detuve en los primeros {_LIMITE}"

        return Resultado(
            ok=True,
            resumen=resumen,
            datos={
                "ruta": str(raiz),
                "total": len(encontrados),
                "bytes_total": total_bytes,
                "items": encontrados,
            },
        )
