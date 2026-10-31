"""Revertir operaciones registradas en el diario."""

from __future__ import annotations

import shutil
from pathlib import Path

from asistente.undo.diario import Diario, Operacion
from asistente.undo.respaldo import destino_libre, restaurar


def revertir(operacion: Operacion, diario: Diario) -> tuple[bool, str]:
    """Deshace una operación. Devuelve `(ok, mensaje en español)`."""
    try:
        if operacion.tipo in {"mover", "renombrar"}:
            destino, origen = Path(operacion.destino), Path(operacion.origen)
            if not destino.exists():
                return False, f"Ya no está en {destino}; no puedo devolverlo."
            restaurar(destino, destino_libre(origen))
            mensaje = f"Devolví {origen.name} a su sitio."

        elif operacion.tipo == "copiar":
            copia = Path(operacion.destino)
            if not copia.exists():
                return False, f"La copia {copia} ya no existe."
            if copia.is_dir():
                shutil.rmtree(copia)
            else:
                copia.unlink()
            mensaje = f"Eliminé la copia {copia.name}."

        elif operacion.tipo == "crear_carpeta":
            carpeta = Path(operacion.destino)
            if not carpeta.exists():
                return False, f"La carpeta {carpeta} ya no existe."
            # Solo si sigue vacía: si el usuario metió cosas, no las borramos.
            if any(carpeta.iterdir()):
                return False, (
                    f"No borro {carpeta}: ya tiene archivos dentro."
                )
            carpeta.rmdir()
            mensaje = f"Eliminé la carpeta vacía {carpeta.name}."

        elif operacion.tipo == "papelera":
            guardado, original = Path(operacion.destino), Path(operacion.origen)
            if not guardado.exists():
                return False, "El archivo ya no está en la papelera."
            restaurar(guardado, destino_libre(original))
            mensaje = f"Recuperé {original.name} de la papelera."

        else:
            return False, f"No sé deshacer una operación de tipo '{operacion.tipo}'."

    except (OSError, shutil.Error) as exc:
        return False, f"No pude deshacer: {exc}"

    diario.marcar_deshecha(operacion.id)
    return True, mensaje
