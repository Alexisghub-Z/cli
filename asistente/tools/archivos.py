"""Herramientas que modifican archivos: mover, copiar, renombrar, crear, papelera.

Todas son de nivel CONFIRMACION y registran la operación en el diario
para que `deshacer` pueda revertirlas.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from asistente.config import Config
from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.registro import registrar
from asistente.undo.diario import Diario, Operacion
from asistente.undo.respaldo import destino_libre, enviar_a_papelera


def _diario() -> Diario:
    return Diario(Config().ruta_diario)


class _ConOrigenYDestino(BaseModel):
    origen: str = Field(description="Ruta del archivo o carpeta de origen.")
    destino: str = Field(description="Ruta de destino.")


@registrar
class Mover(Herramienta):
    nombre = "mover"
    descripcion = (
        "Mueve un archivo o carpeta a otra ubicación. Úsala para reorganizar "
        "archivos. Si el destino es una carpeta existente, mueve dentro de ella."
    )
    nivel = Nivel.CONFIRMACION
    Params = _ConOrigenYDestino

    def run(self, params: _ConOrigenYDestino) -> Resultado:  # type: ignore[override]
        origen, destino = resolver(params.origen), resolver(params.destino)

        if not origen.exists():
            return Resultado.error(
                f"No existe el origen: {origen}. Comprueba la ruta, o usa "
                "buscar_archivos si no sabes dónde está."
            )
        if destino.is_dir():
            destino = destino / origen.name
        if origen == destino:
            return Resultado.error(
                "El origen y el destino son el mismo; no hay nada que mover."
            )
        if destino.exists():
            destino = destino_libre(destino)

        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origen), str(destino))
        except (OSError, shutil.Error) as exc:
            return Resultado.error(
                f"No pude mover {origen.name}: {exc}. Comprueba que tienes "
                "permiso de escritura en la carpeta de destino."
            )

        _diario().registrar(
            Operacion(tipo="mover", origen=str(origen), destino=str(destino))
        )
        return Resultado(
            ok=True,
            resumen=f"Moví {origen.name} a {destino}",
            datos={"origen": str(origen), "destino": str(destino)},
            reversible=True,
        )


@registrar
class Copiar(Herramienta):
    nombre = "copiar"
    descripcion = (
        "Copia un archivo o carpeta a otra ubicación, dejando el original."
    )
    nivel = Nivel.CONFIRMACION
    Params = _ConOrigenYDestino

    def run(self, params: _ConOrigenYDestino) -> Resultado:  # type: ignore[override]
        origen, destino = resolver(params.origen), resolver(params.destino)

        if not origen.exists():
            return Resultado.error(
                f"No existe el origen: {origen}. Comprueba la ruta, o usa "
                "buscar_archivos si no sabes dónde está."
            )
        if destino.is_dir():
            destino = destino / origen.name
        if destino.exists():
            destino = destino_libre(destino)

        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if origen.is_dir():
                shutil.copytree(origen, destino)
            else:
                shutil.copy2(origen, destino)
        except (OSError, shutil.Error) as exc:
            return Resultado.error(
                f"No pude copiar {origen.name}: {exc}. Puede faltar espacio en "
                "disco o permiso de escritura en el destino."
            )

        _diario().registrar(
            Operacion(tipo="copiar", origen=str(origen), destino=str(destino))
        )
        return Resultado(
            ok=True,
            resumen=f"Copié {origen.name} a {destino}",
            datos={"origen": str(origen), "destino": str(destino)},
            reversible=True,
        )


@registrar
class Renombrar(Herramienta):
    nombre = "renombrar"
    descripcion = (
        "Cambia el nombre de un archivo o carpeta, dejándolo en el mismo sitio."
    )
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        ruta: str = Field(description="Ruta del archivo o carpeta a renombrar.")
        nombre_nuevo: str = Field(
            description="Nuevo nombre, sin la ruta. Por ejemplo 'informe.pdf'."
        )

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        origen = resolver(params.ruta)
        nombre = params.nombre_nuevo.strip()

        if not origen.exists():
            return Resultado.error(
                f"No existe: {origen}. Comprueba la ruta con info_archivo."
            )
        # Un nombre con separadores sería un movimiento disfrazado, y eso
        # podría sacar el archivo de la carpeta autorizada.
        if "/" in nombre or "\\" in nombre or nombre in {".", ".."}:
            return Resultado.error(
                f"«{nombre}» no es un nombre válido. Para cambiar de carpeta usa mover."
            )

        destino = origen.with_name(nombre)
        if destino.exists():
            return Resultado.error(
                f"Ya existe algo llamado {nombre} en esa carpeta. "
                "Elige otro nombre."
            )

        try:
            origen.rename(destino)
        except OSError as exc:
            return Resultado.error(
                f"No pude renombrar {origen.name}: {exc}. Comprueba que el "
                "archivo no esté abierto en otro programa."
            )

        _diario().registrar(
            Operacion(tipo="renombrar", origen=str(origen), destino=str(destino))
        )
        return Resultado(
            ok=True,
            resumen=f"Renombré {origen.name} a {nombre}",
            datos={"origen": str(origen), "destino": str(destino)},
            reversible=True,
        )


@registrar
class CrearCarpeta(Herramienta):
    nombre = "crear_carpeta"
    descripcion = "Crea una carpeta nueva, incluidas las carpetas intermedias."
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        ruta: str = Field(description="Ruta de la carpeta a crear.")

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        destino = resolver(params.ruta)

        if destino.exists():
            return Resultado.error(
                f"Ya existe: {destino}. Si quieres ver qué contiene, usa "
                "listar_directorio."
            )

        try:
            destino.mkdir(parents=True)
        except OSError as exc:
            return Resultado.error(
                f"No pude crear la carpeta: {exc}. Comprueba que tienes "
                "permiso de escritura en la carpeta que la contiene."
            )

        _diario().registrar(
            Operacion(tipo="crear_carpeta", destino=str(destino))
        )
        return Resultado(
            ok=True,
            resumen=f"Creé la carpeta {destino}",
            datos={"destino": str(destino)},
            reversible=True,
        )


@registrar
class EnviarAPapelera(Herramienta):
    nombre = "enviar_a_papelera"
    descripcion = (
        "Envía un archivo o carpeta a la papelera del asistente. "
        "Es reversible con el comando deshacer. Usa esto en lugar de borrar."
    )
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        ruta: str = Field(description="Ruta del archivo o carpeta a desechar.")

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        origen = resolver(params.ruta)
        if not origen.exists():
            return Resultado.error(
                f"No existe: {origen}. Comprueba la ruta con info_archivo."
            )

        config = Config()
        try:
            guardado = enviar_a_papelera(origen, config.ruta_papelera)
        except (OSError, shutil.Error) as exc:
            return Resultado.error(
                f"No pude enviar {origen.name} a la papelera: {exc}. "
                "Comprueba que no esté abierto en otro programa."
            )

        _diario().registrar(
            Operacion(tipo="papelera", origen=str(origen), destino=guardado)
        )
        return Resultado(
            ok=True,
            resumen=f"Envié {origen.name} a la papelera (reversible con deshacer)",
            datos={"origen": str(origen), "papelera": guardado},
            reversible=True,
        )
