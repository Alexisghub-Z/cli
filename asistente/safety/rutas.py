"""Rutas protegidas: lugares que el asistente nunca debe modificar.

Multiplataforma vía `pathlib`; sin rutas fijas de un solo sistema.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Prefijos protegidos por sistema operativo. Se comparan ya resueltos.
_PREFIJOS: dict[str, tuple[str, ...]] = {
    "linux": ("/boot", "/dev", "/etc", "/proc", "/sys", "/usr", "/bin",
              "/sbin", "/lib", "/lib64", "/var", "/opt", "/run", "/srv"),
    "darwin": ("/System", "/Library", "/usr", "/bin", "/sbin", "/private",
               "/Applications", "/Volumes"),
    "win32": (r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)",
              r"C:\ProgramData"),
}

# Carpetas dentro del home que tampoco se tocan (configuración sensible).
_HOME_PROTEGIDO: tuple[str, ...] = (
    ".ssh", ".gnupg", ".aws", ".config/gcloud", ".kube", ".docker",
    ".password-store", ".local/share/keyrings", ".mozilla", ".thunderbird",
    ".git-credentials", ".netrc", ".npmrc", ".pypirc", ".claude",
    "AppData",  # Windows
    "Library",  # macOS dentro del home
)


def _prefijos_sistema() -> tuple[str, ...]:
    for clave, valores in _PREFIJOS.items():
        if sys.platform.startswith(clave):
            return valores
    return _PREFIJOS["linux"]


def resolver(ruta: str | Path) -> Path:
    """Expande `~`, variables y symlinks para comparar de forma segura."""
    import os

    texto = os.path.expandvars(str(ruta))
    try:
        return Path(texto).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(texto).expanduser().absolute()


def es_protegida(ruta: str | Path) -> tuple[bool, str]:
    """Indica si una ruta está protegida y por qué.

    Devuelve `(True, motivo)` cuando no se debe modificar.
    """
    destino = resolver(ruta)
    home = Path.home().resolve()

    if destino == home:
        return True, "Es tu carpeta personal completa; elige algo más concreto."
    if destino == Path(destino.anchor):
        return True, "Es la raíz del sistema de archivos."

    # Symlink que apunta fuera: se evalúa el destino real (ya resuelto).
    for prefijo in _prefijos_sistema():
        base = Path(prefijo)
        if destino == base or base in destino.parents:
            return True, f"Pertenece al sistema operativo ({prefijo})."

    for relativo in _HOME_PROTEGIDO:
        base = (home / relativo).resolve()
        if destino == base or base in destino.parents:
            return True, f"Es configuración sensible (~/{relativo})."

    return False, ""


def dentro_de(ruta: str | Path, base: str | Path) -> bool:
    """`True` si `ruta` queda dentro de `base` (evita escapes con `..`)."""
    destino, raiz = resolver(ruta), resolver(base)
    return destino == raiz or raiz in destino.parents
