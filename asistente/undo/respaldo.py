"""Respaldos y papelera propia del asistente.

El borrado permanente está bloqueado; en su lugar los archivos van a una
papelera dentro del directorio de datos del usuario, de donde se pueden
recuperar con `deshacer`.
"""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path


def _sufijo_unico() -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def respaldar(ruta: Path, carpeta_respaldos: Path) -> str:
    """Copia `ruta` a la carpeta de respaldos y devuelve el destino.

    Se usa antes de sobrescribir algo, para poder revertirlo.
    """
    carpeta_respaldos.mkdir(parents=True, exist_ok=True)
    destino = carpeta_respaldos / f"{ruta.name}.{_sufijo_unico()}"
    if ruta.is_dir():
        shutil.copytree(ruta, destino)
    else:
        shutil.copy2(ruta, destino)
    return str(destino)


def enviar_a_papelera(ruta: Path, carpeta_papelera: Path) -> str:
    """Mueve `ruta` a la papelera del asistente y devuelve el destino."""
    carpeta_papelera.mkdir(parents=True, exist_ok=True)
    destino = carpeta_papelera / f"{ruta.name}.{_sufijo_unico()}"
    shutil.move(str(ruta), str(destino))
    return str(destino)


def restaurar(desde: Path, hacia: Path) -> None:
    """Devuelve un archivo de la papelera o de un respaldo a su sitio."""
    hacia.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(desde), str(hacia))


def destino_libre(destino: Path) -> Path:
    """Si `destino` ya existe, añade un sufijo numérico en lugar de pisarlo."""
    if not destino.exists():
        return destino
    base, extension = destino.stem, destino.suffix
    for indice in range(1, 1000):
        candidato = destino.with_name(f"{base}-{indice}{extension}")
        if not candidato.exists():
            return candidato
    return destino.with_name(f"{base}-{_sufijo_unico()}{extension}")
