"""Qué es una receta y cómo se guarda.

Una receta es una secuencia de llamadas a herramientas que salió bien y
que se puede repetir. Guarda el *nombre* de la herramienta y sus
parámetros, nunca un comando de shell: al reproducirla vuelve a pasar por
el sistema de permisos, igual que si la pidiera el modelo.

Los parámetros admiten huecos con `{nombre}`, que se rellenan al
ejecutar: así «organiza mis descargas» sirve para cualquier carpeta.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_HUECO = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# Herramientas que no se guardan en una receta: no tiene sentido repetir
# una consulta, y un comando de shell arbitrario no es reproducible con
# garantías.
_NO_GUARDABLES = frozenset(
    {
        "listar_directorio",
        "buscar_archivos",
        "leer_archivo",
        "info_archivo",
        "espacio_en_disco",
        "procesos",
        "ejecutar_comando",
    }
)


@dataclass
class PasoReceta:
    """Una llamada a herramienta dentro de una receta."""

    herramienta: str
    argumentos: dict[str, Any] = field(default_factory=dict)
    descripcion: str = ""

    def huecos(self) -> set[str]:
        """Nombres de los parámetros que hay que rellenar."""
        encontrados: set[str] = set()
        for valor in self.argumentos.values():
            if isinstance(valor, str):
                encontrados.update(_HUECO.findall(valor))
        return encontrados

    def resolver(self, valores: dict[str, str]) -> dict[str, Any]:
        """Sustituye los huecos por los valores dados."""
        resueltos: dict[str, Any] = {}
        for clave, valor in self.argumentos.items():
            if isinstance(valor, str):
                resueltos[clave] = _HUECO.sub(
                    lambda m: valores.get(m.group(1), m.group(0)), valor
                )
            else:
                resueltos[clave] = valor
        return resueltos


@dataclass
class Receta:
    """Una tarea guardada para repetirla."""

    nombre: str
    descripcion: str = ""
    pasos: list[PasoReceta] = field(default_factory=list)
    creada: float = field(default_factory=time.time)
    veces_usada: int = 0

    def huecos(self) -> list[str]:
        """Todos los parámetros que pide la receta, en orden de aparición."""
        vistos: list[str] = []
        for paso in self.pasos:
            for hueco in sorted(paso.huecos()):
                if hueco not in vistos:
                    vistos.append(hueco)
        return vistos

    def resumen(self) -> str:
        """Descripción corta para listarla."""
        cuantos = len(self.pasos)
        plural = "paso" if cuantos == 1 else "pasos"
        texto = f"{self.nombre}: {cuantos} {plural}"
        if self.descripcion:
            texto += f" — {self.descripcion}"
        return texto


def nombre_valido(nombre: str) -> tuple[bool, str]:
    """Comprueba que el nombre sirva como nombre de archivo."""
    limpio = nombre.strip()
    if not limpio:
        return False, "El nombre no puede estar vacío."
    if len(limpio) > 60:
        return False, "El nombre es demasiado largo (máximo 60 caracteres)."
    # Debe poder usarse como nombre de archivo en cualquier sistema.
    if not re.fullmatch(r"[\w áéíóúüñÁÉÍÓÚÜÑ-]+", limpio):
        return False, (
            "Usa solo letras, números, espacios, guiones y guiones bajos."
        )
    return True, ""


def archivo_de(nombre: str) -> str:
    """Nombre de archivo para una receta."""
    return re.sub(r"[^\w-]+", "-", nombre.strip().lower()).strip("-") + ".json"


def desde_pasos(
    nombre: str, pasos_ejecutados: list, descripcion: str = ""
) -> tuple[Receta | None, str]:
    """Construye una receta a partir de los pasos de una ejecución.

    Devuelve `(receta, "")` o `(None, motivo)` si no hay nada guardable.
    """
    guardables: list[PasoReceta] = []
    omitidas: set[str] = set()

    for paso in pasos_ejecutados:
        herramienta = getattr(paso, "herramienta", "")
        resultado = getattr(paso, "resultado", None)
        # Solo los pasos que funcionaron: una receta repite lo que salió bien.
        if resultado is not None and not getattr(resultado, "ok", False):
            continue
        if herramienta in _NO_GUARDABLES:
            omitidas.add(herramienta)
            continue
        guardables.append(
            PasoReceta(
                herramienta=herramienta,
                argumentos=dict(getattr(paso, "argumentos", {}) or {}),
                descripcion=getattr(resultado, "resumen", "") or "",
            )
        )

    if not guardables:
        if omitidas:
            lista = ", ".join(sorted(omitidas))
            return None, (
                f"No hay nada que guardar: esa tarea solo consultó "
                f"información ({lista}). Las recetas sirven para repetir "
                "acciones que modifican archivos."
            )
        return None, "No hay pasos que guardar."

    return Receta(nombre=nombre.strip(), descripcion=descripcion, pasos=guardables), ""


def guardar(receta: Receta, carpeta: Path) -> Path:
    """Escribe la receta en disco como JSON."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / archivo_de(receta.nombre)
    destino.write_text(
        json.dumps(asdict(receta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destino


def cargar(ruta: Path) -> Receta | None:
    """Lee una receta de disco. `None` si el archivo no es válido."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(datos, dict) or not datos.get("nombre"):
        return None

    pasos = []
    for crudo in datos.get("pasos") or []:
        if not isinstance(crudo, dict) or not crudo.get("herramienta"):
            continue
        argumentos = crudo.get("argumentos") or {}
        pasos.append(
            PasoReceta(
                herramienta=str(crudo["herramienta"]),
                argumentos=argumentos if isinstance(argumentos, dict) else {},
                descripcion=str(crudo.get("descripcion") or ""),
            )
        )
    if not pasos:
        return None

    return Receta(
        nombre=str(datos["nombre"]),
        descripcion=str(datos.get("descripcion") or ""),
        pasos=pasos,
        creada=float(datos.get("creada") or time.time()),
        veces_usada=int(datos.get("veces_usada") or 0),
    )


def todas(carpeta: Path) -> list[Receta]:
    """Todas las recetas guardadas, por nombre."""
    if not carpeta.is_dir():
        return []
    recetas = [
        receta
        for ruta in sorted(carpeta.glob("*.json"))
        if (receta := cargar(ruta)) is not None
    ]
    return sorted(recetas, key=lambda r: r.nombre.lower())


def buscar(nombre: str, carpeta: Path) -> Receta | None:
    """Busca una receta por nombre, sin distinguir mayúsculas."""
    directa = carpeta / archivo_de(nombre)
    if directa.is_file():
        return cargar(directa)
    objetivo = nombre.strip().lower()
    for receta in todas(carpeta):
        if receta.nombre.lower() == objetivo:
            return receta
    return None
