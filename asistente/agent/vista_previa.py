"""Vista previa de los cambios: qué pasaría, sin tocar el disco.

Se calcula a partir de los parámetros ya validados, antes de pedir
confirmación, para que el usuario decida viendo el efecto real y no solo
el nombre de la herramienta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from asistente.safety.rutas import resolver
from asistente.tools.listar import formato_tamano


@dataclass
class Cambio:
    """Un efecto concreto que tendría la acción."""

    # crear | modificar | mover | eliminar | ejecutar | leer
    tipo: str
    detalle: str
    aviso: str = ""


@dataclass
class VistaPrevia:
    """Lo que ocurriría al ejecutar una herramienta."""

    titulo: str
    cambios: list[Cambio] = field(default_factory=list)
    reversible: bool = True

    @property
    def avisos(self) -> list[str]:
        return [c.aviso for c in self.cambios if c.aviso]


def _tamano(ruta: Path) -> str:
    try:
        if ruta.is_dir():
            total = sum(
                f.stat().st_size for f in ruta.rglob("*") if f.is_file()
            )
            cuantos = sum(1 for _ in ruta.rglob("*"))
            return f"carpeta con {cuantos} elementos, {formato_tamano(total)}"
        return formato_tamano(ruta.stat().st_size)
    except OSError:
        return "tamaño desconocido"


def _destino_real(origen: Path, destino: Path) -> Path:
    """Replica la resolución del destino que hacen mover y copiar."""
    if destino.is_dir():
        return destino / origen.name
    return destino


def _colision(destino: Path) -> str:
    """Aviso si el destino ya existe (no se pisa: se añade sufijo)."""
    if destino.exists():
        return (
            f"Ya existe {destino.name}; guardaré el nuevo con otro nombre "
            "en lugar de reemplazarlo."
        )
    return ""


def calcular(nombre: str, params: BaseModel) -> VistaPrevia | None:
    """Describe el efecto de una herramienta. `None` si no modifica nada."""
    if nombre in {"mover", "copiar"}:
        origen = resolver(getattr(params, "origen"))
        destino = _destino_real(origen, resolver(getattr(params, "destino")))
        verbo = "Mover" if nombre == "mover" else "Copiar"
        cambios = [
            Cambio(
                tipo="mover" if nombre == "mover" else "crear",
                detalle=f"{origen} → {destino}",
                aviso=_colision(destino),
            )
        ]
        if origen.exists():
            cambios.append(
                Cambio(tipo="leer", detalle=f"Origen: {_tamano(origen)}")
            )
        if nombre == "mover":
            cambios.append(
                Cambio(
                    tipo="eliminar",
                    detalle=f"{origen.name} dejará de estar en {origen.parent}",
                )
            )
        return VistaPrevia(titulo=f"{verbo} {origen.name}", cambios=cambios)

    if nombre == "renombrar":
        origen = resolver(getattr(params, "ruta"))
        nuevo = getattr(params, "nombre_nuevo")
        destino = origen.with_name(nuevo)
        return VistaPrevia(
            titulo=f"Renombrar {origen.name}",
            cambios=[
                Cambio(
                    tipo="modificar",
                    detalle=f"{origen.name} → {nuevo}",
                    aviso=(
                        f"Ya existe {nuevo} en esa carpeta."
                        if destino.exists()
                        else ""
                    ),
                ),
                Cambio(tipo="leer", detalle=f"En {origen.parent}"),
            ],
        )

    if nombre == "crear_carpeta":
        destino = resolver(getattr(params, "ruta"))
        # Avisa de las carpetas intermedias que también se crearán.
        faltantes = [p for p in reversed(destino.parents) if not p.exists()]
        cambios = [Cambio(tipo="crear", detalle=f"Nueva carpeta: {destino}")]
        if faltantes:
            nombres = ", ".join(str(p) for p in faltantes)
            cambios.append(
                Cambio(
                    tipo="crear",
                    detalle=f"También se crearán las carpetas intermedias: {nombres}",
                )
            )
        return VistaPrevia(titulo="Crear carpeta", cambios=cambios)

    if nombre == "enviar_a_papelera":
        origen = resolver(getattr(params, "ruta"))
        return VistaPrevia(
            titulo=f"Enviar {origen.name} a la papelera",
            cambios=[
                Cambio(
                    tipo="eliminar",
                    detalle=f"{origen} ({_tamano(origen)})",
                    aviso="No se borra: podrás recuperarlo con «asistente deshacer».",
                )
            ],
        )

    if nombre == "ejecutar_comando":
        comando = getattr(params, "comando")
        carpeta = resolver(getattr(params, "carpeta", "."))
        return VistaPrevia(
            titulo="Ejecutar un comando de terminal",
            cambios=[
                Cambio(tipo="ejecutar", detalle=comando),
                Cambio(tipo="leer", detalle=f"En la carpeta {carpeta}"),
            ],
            # No podemos saber qué hace un comando arbitrario.
            reversible=False,
        )

    return None
