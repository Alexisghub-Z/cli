"""Herramienta: metadatos de un archivo o carpeta."""

from __future__ import annotations

import stat as stat_mod
import time
from pathlib import Path

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.listar import formato_tamano
from asistente.tools.registro import registrar

# Extensiones frecuentes, para describir el tipo en español.
_TIPOS: dict[str, str] = {
    ".txt": "texto", ".md": "texto Markdown", ".pdf": "documento PDF",
    ".doc": "documento Word", ".docx": "documento Word",
    ".xls": "hoja de cálculo", ".xlsx": "hoja de cálculo",
    ".ppt": "presentación", ".pptx": "presentación",
    ".jpg": "imagen JPEG", ".jpeg": "imagen JPEG", ".png": "imagen PNG",
    ".gif": "imagen GIF", ".svg": "imagen vectorial", ".webp": "imagen WebP",
    ".mp3": "audio MP3", ".wav": "audio WAV", ".flac": "audio FLAC",
    ".mp4": "vídeo MP4", ".mkv": "vídeo MKV", ".avi": "vídeo AVI",
    ".zip": "archivo comprimido ZIP", ".tar": "archivo TAR",
    ".gz": "archivo comprimido gzip", ".bz2": "archivo comprimido bzip2",
    ".xz": "archivo comprimido xz", ".7z": "archivo comprimido 7z",
    ".py": "código Python", ".js": "código JavaScript",
    ".ts": "código TypeScript", ".html": "página HTML", ".css": "hoja CSS",
    ".json": "datos JSON", ".yaml": "datos YAML", ".yml": "datos YAML",
    ".toml": "configuración TOML", ".csv": "tabla CSV",
    ".sh": "guion de shell", ".c": "código C", ".cpp": "código C++",
    ".rs": "código Rust", ".go": "código Go", ".java": "código Java",
}


def describir_tipo(ruta: Path) -> str:
    """Tipo legible en español, a partir de la extensión."""
    if ruta.is_dir():
        return "carpeta"
    if ruta.is_symlink():
        return "enlace simbólico"
    sufijo = ruta.suffix.lower()
    if sufijo in _TIPOS:
        return _TIPOS[sufijo]
    return f"archivo {sufijo.lstrip('.')}" if sufijo else "archivo sin extensión"


def _fecha(momento: float) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(momento))


def _hace_cuanto(momento: float) -> str:
    """Antigüedad en español, redondeada a la unidad más natural."""
    segundos = max(0, time.time() - momento)
    if segundos < 60:
        return "hace unos segundos"
    minutos = segundos / 60
    if minutos < 60:
        return f"hace {int(minutos)} minutos"
    horas = minutos / 60
    if horas < 24:
        return f"hace {int(horas)} horas"
    dias = horas / 24
    if dias < 31:
        return f"hace {int(dias)} días"
    meses = dias / 30.44
    if meses < 12:
        return f"hace {int(meses)} meses"
    return f"hace {dias / 365.25:.1f} años"


@registrar
class InfoArchivo(Herramienta):
    nombre = "info_archivo"
    descripcion = (
        "Muestra solo los datos técnicos de un archivo o carpeta: cuánto "
        "pesa, de qué tipo es, cuándo se modificó y sus permisos. Úsala "
        "cuando pregunten el tamaño, la fecha o los permisos. NO abre el "
        "archivo ni muestra su contenido ni de qué trata: para abrirlo, "
        "leerlo o saber de qué trata usa siempre leer_archivo."
    )
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        ruta: str = Field(
            description="Ruta del archivo o carpeta, por ejemplo '~/notas.txt'."
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        destino = resolver(params.ruta)

        if not destino.exists():
            return Resultado.error(
                f"No existe: {destino}. Comprueba la ruta, o usa "
                "buscar_archivos si no sabes dónde está."
            )

        try:
            datos = destino.stat()
        except OSError as exc:
            return Resultado.error(f"No pude leer los datos de {destino}: {exc}")

        tipo = describir_tipo(destino)
        es_carpeta = destino.is_dir()

        # En carpetas, el tamaño útil es el del contenido, no el del inodo.
        contenido: dict[str, int] = {}
        if es_carpeta:
            total = archivos = carpetas = 0
            try:
                for elemento in destino.rglob("*"):
                    try:
                        if elemento.is_dir():
                            carpetas += 1
                        else:
                            archivos += 1
                            total += elemento.stat().st_size
                    except OSError:
                        continue
            except OSError:
                pass
            contenido = {
                "archivos": archivos,
                "carpetas": carpetas,
                "bytes": total,
            }
            tamano, tamano_legible = total, formato_tamano(total)
        else:
            tamano, tamano_legible = datos.st_size, formato_tamano(datos.st_size)

        permisos = stat_mod.filemode(datos.st_mode)
        resultado: dict = {
            "ruta": str(destino),
            "nombre": destino.name,
            "tipo": tipo,
            "tamano": tamano,
            "tamano_legible": tamano_legible,
            "modificado": _fecha(datos.st_mtime),
            "modificado_hace": _hace_cuanto(datos.st_mtime),
            "creado": _fecha(datos.st_ctime),
            "permisos": permisos,
            "legible": destino.is_file() or es_carpeta,
            "escribible": bool(datos.st_mode & stat_mod.S_IWUSR),
        }
        if contenido:
            resultado["contenido"] = contenido

        if es_carpeta:
            resumen = (
                f"{destino.name}: carpeta con {contenido['archivos']} archivos "
                f"y {contenido['carpetas']} subcarpetas, {tamano_legible}, "
                f"modificada {resultado['modificado_hace']}"
            )
        else:
            resumen = (
                f"{destino.name}: {tipo}, {tamano_legible}, "
                f"modificado {resultado['modificado_hace']}"
            )

        return Resultado(ok=True, resumen=resumen, datos=resultado)
