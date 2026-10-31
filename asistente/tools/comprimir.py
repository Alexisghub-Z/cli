"""Herramientas: comprimir y descomprimir archivos (ZIP y TAR).

Al descomprimir se verifica cada entrada antes de extraerla: un archivo
malicioso puede traer nombres como `../../.ssh/authorized_keys` para
escribir fuera de la carpeta destino (ataque conocido como *zip slip*).
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from pydantic import BaseModel, Field

from asistente.config import Config
from asistente.safety.permisos import Nivel
from asistente.safety.rutas import dentro_de, es_protegida, resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.listar import formato_tamano
from asistente.tools.registro import registrar
from asistente.undo.diario import Diario, Operacion
from asistente.undo.respaldo import destino_libre

# Límites para no llenar el disco con una bomba de descompresión.
_MAX_DESCOMPRIMIDO = 2 * 1024 * 1024 * 1024  # 2 GB
_MAX_ENTRADAS = 20_000

_FORMATOS_TAR = {
    ".tar": "", ".gz": "gz", ".tgz": "gz", ".bz2": "bz2",
    ".tbz2": "bz2", ".xz": "xz", ".txz": "xz",
}


def _diario() -> Diario:
    return Diario(Config().ruta_diario)


def _es_tar(ruta: Path) -> bool:
    nombre = ruta.name.lower()
    return nombre.endswith(
        (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
    )


def entrada_segura(nombre: str, destino: Path) -> tuple[bool, str]:
    """Comprueba que una entrada del archivo no escape de `destino`.

    Rechaza rutas absolutas, `..` y enlaces que apunten fuera. Es la
    defensa contra el *zip slip*.
    """
    if not nombre or nombre in {".", ".."}:
        return False, "nombre vacío o inválido"

    candidato = Path(nombre)
    if candidato.is_absolute() or nombre.startswith(("/", "\\")):
        return False, f"«{nombre}» es una ruta absoluta"
    # Windows: también C:\... o \\servidor\...
    if len(nombre) > 1 and nombre[1] == ":":
        return False, f"«{nombre}» lleva una unidad de disco"
    if ".." in candidato.parts:
        return False, f"«{nombre}» intenta salir de la carpeta destino"

    # Comprobación definitiva: la ruta final debe quedar dentro.
    if not dentro_de(destino / nombre, destino):
        return False, f"«{nombre}» quedaría fuera de la carpeta destino"
    return True, ""


@registrar
class Comprimir(Herramienta):
    nombre = "comprimir"
    descripcion = (
        "Comprime un archivo o carpeta en un ZIP. Úsala cuando el usuario "
        "quiera empaquetar, comprimir o reducir el tamaño de varios archivos."
    )
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        origen: str = Field(
            description="Archivo o carpeta a comprimir, por ejemplo '~/Fotos'."
        )
        destino: str = Field(
            default="",
            description=(
                "Ruta del ZIP a crear. Si se omite, se crea junto al origen "
                "con el mismo nombre y extensión .zip."
            ),
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        origen = resolver(params.origen)
        if not origen.exists():
            return Resultado.error(
                f"No existe: {origen}. Comprueba la ruta con info_archivo."
            )

        if params.destino:
            destino = resolver(params.destino)
            if destino.suffix.lower() != ".zip":
                destino = destino.with_suffix(".zip")
        else:
            destino = origen.with_suffix(".zip")
        destino = destino_libre(destino)

        archivos: list[Path] = (
            [p for p in origen.rglob("*") if p.is_file()]
            if origen.is_dir()
            else [origen]
        )
        if not archivos:
            return Resultado.error(
                f"{origen.name} está vacío; no hay nada que comprimir."
            )

        base = origen.parent if origen.is_file() else origen
        original = 0
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(
                destino, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as paquete:
                for archivo in archivos:
                    try:
                        original += archivo.stat().st_size
                        paquete.write(archivo, archivo.relative_to(base))
                    except OSError:
                        continue  # archivo ilegible: se omite, no se aborta
        except (OSError, zipfile.BadZipFile) as exc:
            destino.unlink(missing_ok=True)
            return Resultado.error(f"No pude crear el ZIP: {exc}")

        comprimido = destino.stat().st_size
        ahorro = (1 - comprimido / original) * 100 if original else 0.0

        _diario().registrar(
            Operacion(tipo="copiar", origen=str(origen), destino=str(destino))
        )
        return Resultado(
            ok=True,
            resumen=(
                f"Comprimí {len(archivos)} archivos en {destino.name}: "
                f"{formato_tamano(original)} → {formato_tamano(comprimido)} "
                f"({ahorro:.0f}% menos)"
            ),
            datos={
                "origen": str(origen),
                "destino": str(destino),
                "archivos": len(archivos),
                "bytes_original": original,
                "bytes_comprimido": comprimido,
                "ahorro_porcentaje": round(ahorro, 1),
            },
            reversible=True,
        )


@registrar
class Descomprimir(Herramienta):
    nombre = "descomprimir"
    descripcion = (
        "Extrae el contenido de un archivo ZIP o TAR en una carpeta. Úsala "
        "cuando el usuario quiera abrir, extraer o descomprimir un paquete."
    )
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        origen: str = Field(description="El archivo ZIP o TAR a extraer.")
        destino: str = Field(
            default="",
            description=(
                "Carpeta donde extraer. Si se omite, se crea una carpeta "
                "con el nombre del archivo, junto a él."
            ),
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        origen = resolver(params.origen)
        if not origen.is_file():
            return Resultado.error(
                f"No existe el archivo: {origen}. Comprueba la ruta."
            )

        destino = (
            resolver(params.destino)
            if params.destino
            else origen.parent / origen.name.split(".")[0]
        )

        protegida, motivo = es_protegida(destino)
        if protegida:
            return Resultado.error(
                f"No extraigo en «{destino}»: {motivo} "
                "Elige una carpeta de tu directorio personal."
            )

        es_tar = _es_tar(origen)
        if not es_tar and not zipfile.is_zipfile(origen):
            return Resultado.error(
                f"{origen.name} no parece un ZIP ni un TAR. "
                "Comprueba el archivo; puede estar corrupto."
            )

        try:
            if es_tar:
                nombres, total = self._inspeccionar_tar(origen)
            else:
                nombres, total = self._inspeccionar_zip(origen)
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
            return Resultado.error(
                f"No pude leer {origen.name}: {exc}. Puede estar corrupto."
            )

        if not nombres:
            return Resultado.error(f"{origen.name} está vacío.")
        if len(nombres) > _MAX_ENTRADAS:
            return Resultado.error(
                f"{origen.name} tiene {len(nombres)} entradas, demasiadas "
                f"(el límite es {_MAX_ENTRADAS})."
            )
        if total > _MAX_DESCOMPRIMIDO:
            return Resultado.error(
                f"Descomprimido ocuparía {formato_tamano(total)}, más del "
                f"límite de {formato_tamano(_MAX_DESCOMPRIMIDO)}."
            )

        # Zip slip: se verifica TODO antes de extraer nada.
        for nombre in nombres:
            seguro, razon = entrada_segura(nombre, destino)
            if not seguro:
                return Resultado.error(
                    f"No extraigo {origen.name}: contiene una entrada "
                    f"peligrosa ({razon}). El archivo podría estar preparado "
                    "para escribir fuera de la carpeta destino."
                )

        destino.mkdir(parents=True, exist_ok=True)
        try:
            if es_tar:
                modo = "r:" + _FORMATOS_TAR.get(origen.suffix.lower(), "")
                with tarfile.open(origen, modo.rstrip(":")) as paquete:
                    seguros = [
                        m for m in paquete.getmembers() if m.isfile() or m.isdir()
                    ]
                    # filter="data" rechaza rutas absolutas, enlaces que
                    # escapan y metadatos peligrosos. Será el valor por
                    # defecto en Python 3.14; lo fijamos para que el
                    # comportamiento sea el mismo en 3.11-3.13.
                    paquete.extractall(destino, members=seguros, filter="data")
            else:
                with zipfile.ZipFile(origen) as paquete:
                    paquete.extractall(destino)
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
            return Resultado.error(f"Falló la extracción: {exc}")

        _diario().registrar(
            Operacion(
                tipo="crear_carpeta",
                destino=str(destino),
                extra={"desde": str(origen)},
            )
        )
        return Resultado(
            ok=True,
            resumen=(
                f"Extraje {len(nombres)} elementos de {origen.name} "
                f"en {destino} ({formato_tamano(total)})"
            ),
            datos={
                "origen": str(origen),
                "destino": str(destino),
                "entradas": len(nombres),
                "bytes": total,
            },
            reversible=True,
        )

    @staticmethod
    def _inspeccionar_zip(ruta: Path) -> tuple[list[str], int]:
        with zipfile.ZipFile(ruta) as paquete:
            info = paquete.infolist()
            return [i.filename for i in info], sum(i.file_size for i in info)

    @staticmethod
    def _inspeccionar_tar(ruta: Path) -> tuple[list[str], int]:
        with tarfile.open(ruta, "r:*") as paquete:
            miembros = paquete.getmembers()
            nombres = [m.name for m in miembros]
            # Un enlace que apunte fuera es otra vía de escape.
            for miembro in miembros:
                if miembro.issym() or miembro.islnk():
                    nombres.append(miembro.linkname)
            return nombres, sum(m.size for m in miembros)
