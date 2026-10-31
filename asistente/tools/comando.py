"""Herramienta: ejecutar un comando de shell, siempre con confirmación.

Es la herramienta más delicada del asistente: muestra el comando exacto y
rechaza de entrada lo que no tiene vuelta atrás o escala privilegios.
"""

from __future__ import annotations

import re
import shlex
import subprocess

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import es_protegida, resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.registro import registrar

_TIEMPO_LIMITE = 60
_MAX_SALIDA = 8000

# Comandos que escalan privilegios: bloqueados sin excepción.
_PRIVILEGIOS = frozenset({"sudo", "su", "doas", "pkexec", "runas", "chown", "chmod"})

# Patrones sin vuelta atrás. El asistente tiene papelera y deshacer; un
# `rm -rf` se los salta, así que no se permite.
_DESTRUCTIVOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+(-\w*\s+)*-?\w*[rf]", re.I), "borrado permanente con rm"),
    (re.compile(r"\b(mkfs|fdisk|parted|diskutil)\b", re.I), "formateo de discos"),
    (re.compile(r"\bdd\b.*\bof=", re.I), "escritura directa en disco con dd"),
    (re.compile(r":\(\)\s*\{.*\}\s*;?\s*:", re.S), "bomba de bifurcación"),
    (re.compile(r">\s*/dev/(sd|nvme|disk)", re.I), "escritura en un disco"),
    (re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b", re.I), "apagado del sistema"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(ba)?sh", re.I), "ejecutar algo descargado"),
    (re.compile(r"\bchmod\s+(-\w+\s+)*777\b", re.I), "permisos abiertos a todos"),
    (re.compile(r"\bhistory\s+-c\b|\bshred\b", re.I), "borrado de rastros"),
)


def revisar_comando(comando: str) -> tuple[bool, str]:
    """Comprueba si un comando es admisible. `(True, motivo)` = rechazado."""
    texto = comando.strip()
    if not texto:
        return True, "El comando está vacío."

    for patron, motivo in _DESTRUCTIVOS:
        if patron.search(texto):
            return True, motivo

    # Revisa cada tramo entre tuberías y encadenamientos, no solo el primero.
    for tramo in re.split(r"\||&&|;|\|\||\n", texto):
        try:
            piezas = shlex.split(tramo)
        except ValueError:
            return True, "No entiendo las comillas del comando."
        if piezas and piezas[0].rsplit("/", 1)[-1].lower() in _PRIVILEGIOS:
            return True, f"usa privilegios de administrador ({piezas[0]})"

    # Rutas protegidas mencionadas como argumento.
    try:
        for pieza in shlex.split(texto):
            if pieza.startswith(("-", "~-")) or "/" not in pieza:
                continue
            protegida, motivo = es_protegida(pieza)
            if protegida:
                return True, f"toca una ruta protegida ({pieza}: {motivo})"
    except ValueError:
        pass

    return False, ""


@registrar
class EjecutarComando(Herramienta):
    nombre = "ejecutar_comando"
    descripcion = (
        "Ejecuta un comando de terminal. Úsala solo cuando ninguna otra "
        "herramienta sirva. Siempre se le muestra el comando al usuario "
        "para que lo apruebe antes de ejecutarse."
    )
    nivel = Nivel.CONFIRMACION

    class Params(BaseModel):
        comando: str = Field(
            description="El comando completo a ejecutar, por ejemplo 'git status'."
        )
        carpeta: str = Field(
            default=".", description="Carpeta donde ejecutarlo."
        )

    def rutas_afectadas(self, params: Params) -> list[str]:  # type: ignore[override]
        return [params.carpeta]

    def run(self, params: Params) -> Resultado:  # type: ignore[override]
        rechazado, motivo = revisar_comando(params.comando)
        if rechazado:
            return Resultado.error(
                f"No ejecuto «{params.comando}»: {motivo}."
            )

        carpeta = resolver(params.carpeta)
        if not carpeta.is_dir():
            return Resultado.error(f"No es una carpeta: {carpeta}")

        try:
            proceso = subprocess.run(
                params.comando,
                shell=True,
                cwd=str(carpeta),
                capture_output=True,
                text=True,
                timeout=_TIEMPO_LIMITE,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Resultado.error(
                f"El comando tardó más de {_TIEMPO_LIMITE} segundos y lo corté."
            )
        except OSError as exc:
            return Resultado.error(f"No pude ejecutar el comando: {exc}")

        salida = (proceso.stdout or "")[:_MAX_SALIDA]
        error = (proceso.stderr or "")[:_MAX_SALIDA]
        ok = proceso.returncode == 0

        resumen = (
            f"«{params.comando}» terminó correctamente"
            if ok
            else f"«{params.comando}» falló (código {proceso.returncode})"
        )
        return Resultado(
            ok=ok,
            resumen=resumen,
            datos={
                "comando": params.comando,
                "codigo": proceso.returncode,
                "salida": salida,
                "error": error,
            },
        )
