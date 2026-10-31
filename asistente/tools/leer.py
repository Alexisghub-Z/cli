"""Herramienta: leer el contenido de un archivo de texto."""

from __future__ import annotations

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import es_protegida, resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.listar import formato_tamano
from asistente.tools.registro import registrar

_MAX_BYTES = 256 * 1024  # 256 KB: suficiente para texto, evita llenar el contexto
_MAX_LINEAS = 400


def _parece_binario(muestra: bytes) -> bool:
    """Heurística: un byte nulo casi siempre significa binario."""
    return b"\x00" in muestra


@registrar
class LeerArchivo(Herramienta):
    nombre = "leer_archivo"
    descripcion = (
        "Lee el contenido de un archivo de texto. Úsala cuando el usuario "
        "quiera abrir un archivo, saber qué dice o de qué trata. "
        "No sirve para imágenes ni binarios."
    )
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        ruta: str = Field(description="Ruta del archivo, por ejemplo '~/notas.txt'.")
        max_lineas: int = Field(
            default=_MAX_LINEAS,
            ge=1,
            le=2000,
            description="Máximo de líneas a devolver.",
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        destino = resolver(params.ruta)

        # Leer también se restringe en rutas sensibles: no queremos que el
        # modelo vea claves privadas ni credenciales.
        protegida, motivo = es_protegida(destino)
        if protegida and destino.is_file():
            return Resultado.error(
                f"No voy a leer «{destino}»: {motivo}"
            )

        if not destino.exists():
            return Resultado.error(
                f"No existe el archivo: {destino}. Comprueba la ruta, o usa "
                "buscar_archivos para localizarlo."
            )
        if destino.is_dir():
            return Resultado.error(
                f"Es una carpeta, no un archivo: {destino}. "
                "Usa listar_directorio."
            )

        try:
            tamano = destino.stat().st_size
            with destino.open("rb") as binario:
                crudo = binario.read(_MAX_BYTES)
        except OSError as exc:
            return Resultado.error(
                f"No pude leer {destino}: {exc}. Puede que no tengas permiso "
                "sobre ese archivo."
            )

        if _parece_binario(crudo):
            return Resultado.error(
                f"{destino.name} parece un archivo binario "
                f"({formato_tamano(tamano)}), no texto."
            )

        texto = crudo.decode("utf-8", errors="replace")
        lineas = texto.splitlines()
        recortado = len(lineas) > params.max_lineas or tamano > _MAX_BYTES
        mostradas = lineas[: params.max_lineas]

        resumen = f"{destino.name}: {len(lineas)} líneas, {formato_tamano(tamano)}"
        if recortado:
            resumen += f" (muestro las primeras {len(mostradas)})"

        return Resultado(
            ok=True,
            resumen=resumen,
            datos={
                "ruta": str(destino),
                "lineas": len(lineas),
                "bytes": tamano,
                "recortado": recortado,
                "contenido": "\n".join(mostradas),
            },
        )
