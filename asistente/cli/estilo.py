"""Paleta, símbolos y detección de lo que soporta la terminal.

Todo lo visual de la interfaz sale de aquí, para que la paleta sea una sola:
azules para la marca, verde para éxito, amarillo para advertencias y rojo
para errores.
"""

from __future__ import annotations

import os

from rich.console import Console

# Marca
AZUL_MARINO = "#1E3A8A"
AZUL_CLARO = "#60A5FA"
# Estados
VERDE = "#22C55E"
AMARILLO = "#EAB308"
ROJO = "#EF4444"

# Por debajo de este ancho la mascota se oculta y queda solo el texto.
ANCHO_MINIMO_MASCOTA = 60

# Fuerza el modo sencillo (solo ASCII), útil para probar o para terminales
# que dicen soportar Unicode y luego no lo pintan bien.
VARIABLE_ASCII = "BRUMA_ASCII"


def soporta_unicode(consola: Console) -> bool:
    """True si la terminal puede pintar Unicode (cajas, emoji, la mascota)."""
    if consola.legacy_windows:  # cmd.exe antiguo, sin secuencias VT
        return False
    codificacion = (consola.encoding or "").lower().replace("-", "")
    return codificacion.startswith("utf")


def soporta_color(consola: Console) -> bool:
    """True si la terminal pinta colores y el usuario no los desactivó."""
    if consola.no_color or os.environ.get("NO_COLOR"):
        return False
    return consola.color_system is not None


def modo_simple(consola: Console) -> bool:
    """Modo solo ASCII y sin color, para terminales limitadas."""
    if os.environ.get(VARIABLE_ASCII, "").strip() not in {"", "0"}:
        return True
    return not soporta_unicode(consola) or not soporta_color(consola)


def cabe_mascota(consola: Console) -> bool:
    """La mascota solo aparece si la terminal es lo bastante ancha."""
    return consola.width >= ANCHO_MINIMO_MASCOTA


_SIMBOLOS = {
    # nombre: (unicode, ascii)
    "ok": ("✓", "+"),
    "fallo": ("✗", "x"),
    "aviso": ("⚠", "!"),
    "punto": ("●", "*"),
    "prompt": ("›", ">"),
    "flecha": ("→", "->"),
    "separador": ("·", "|"),
    "carpeta": ("📁", "[d]"),
    "archivo": ("📄", "   "),
}


def simbolo(nombre: str, simple: bool) -> str:
    """Devuelve el símbolo en Unicode o su equivalente ASCII."""
    unicode, ascii_ = _SIMBOLOS[nombre]
    return ascii_ if simple else unicode
