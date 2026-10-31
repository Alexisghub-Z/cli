"""Herramienta: listar el contenido de un directorio."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.registro import registrar

_LIMITE = 200


def formato_tamano(bytes_: int) -> str:
    """Tamaño legible en español (KB, MB, GB)."""
    unidades = ("B", "KB", "MB", "GB", "TB")
    valor = float(bytes_)
    for unidad in unidades:
        if valor < 1024 or unidad == unidades[-1]:
            entero = "%.0f" % valor if unidad == "B" else "%.1f" % valor
            return f"{entero} {unidad}"
        valor /= 1024
    return f"{valor:.1f} TB"


@registrar
class ListarDirectorio(Herramienta):
    nombre = "listar_directorio"
    descripcion = (
        "Lista los archivos y carpetas de un directorio. "
        "Úsala para ver qué contiene una carpeta. Para encontrar un archivo "
        "por su nombre usa buscar_archivos."
    )
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        ruta: str = Field(
            default=".",
            description="Ruta de la carpeta a listar, por ejemplo '~/Descargas'.",
        )
        incluir_ocultos: bool = Field(
            default=False,
            description="Incluir archivos que empiezan con punto.",
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        destino = resolver(params.ruta)

        if not destino.exists():
            return Resultado.error(
                f"No existe la ruta: {destino}. Comprueba cómo se escribe, o "
                "usa buscar_archivos para localizarla."
            )
        if not destino.is_dir():
            return Resultado.error(
                f"No es una carpeta sino un archivo: {destino}. "
                "Usa leer_archivo para ver su contenido."
            )

        try:
            entradas = sorted(
                destino.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            return Resultado.error(
                f"No tengo permiso para leer {destino}. Prueba con una "
                "carpeta de tu directorio personal."
            )

        if not params.incluir_ocultos:
            entradas = [e for e in entradas if not e.name.startswith(".")]

        total = len(entradas)
        items = []
        for entrada in entradas[:_LIMITE]:
            try:
                es_dir = entrada.is_dir()
                tamano = 0 if es_dir else entrada.stat().st_size
            except OSError:
                es_dir, tamano = False, 0
            items.append(
                {
                    "nombre": entrada.name,
                    "tipo": "carpeta" if es_dir else "archivo",
                    "tamano": tamano,
                    "tamano_legible": "—" if es_dir else formato_tamano(tamano),
                }
            )

        carpetas = sum(1 for i in items if i["tipo"] == "carpeta")
        resumen = (
            f"{total} elementos en {destino} "
            f"({carpetas} carpetas, {total - carpetas} archivos)"
        )
        if total > _LIMITE:
            resumen += f"; se muestran los primeros {_LIMITE}"

        return Resultado(
            ok=True,
            resumen=resumen,
            datos={"ruta": str(destino), "total": total, "items": items},
        )
