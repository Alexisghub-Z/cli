"""Diario de operaciones reversibles, en JSONL.

Cada línea es una operación con lo necesario para revertirla. Formato de
texto a propósito: si algo se corrompe, se puede inspeccionar y arreglar
a mano.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Operacion:
    """Una acción que se puede deshacer."""

    tipo: str  # mover | copiar | renombrar | crear_carpeta | papelera
    origen: str = ""
    destino: str = ""
    # Respaldo del archivo que se sobrescribió, si lo hubo.
    respaldo: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    momento: float = field(default_factory=time.time)
    deshecha: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def descripcion(self) -> str:
        """Texto en español para mostrar al usuario."""
        etiquetas = {
            "mover": "Moví",
            "copiar": "Copié",
            "renombrar": "Renombré",
            "crear_carpeta": "Creé la carpeta",
            "papelera": "Envié a la papelera",
        }
        verbo = etiquetas.get(self.tipo, self.tipo)
        if self.tipo == "crear_carpeta":
            return f"{verbo} {self.destino}"
        if self.tipo == "papelera":
            return f"{verbo} {self.origen}"
        return f"{verbo} {self.origen} → {self.destino}"


class Diario:
    """Registro append-only de operaciones reversibles."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta

    def registrar(self, operacion: Operacion) -> Operacion:
        """Añade una operación al diario."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(asdict(operacion), ensure_ascii=False) + "\n")
        return operacion

    def todas(self) -> list[Operacion]:
        """Lee el diario completo, de la más antigua a la más reciente."""
        if not self.ruta.exists():
            return []
        operaciones: list[Operacion] = []
        for linea in self.ruta.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError:
                continue  # línea corrupta: se ignora, no se rompe el deshacer
            campos = {
                k: v for k, v in datos.items() if k in Operacion.__dataclass_fields__
            }
            try:
                operaciones.append(Operacion(**campos))
            except TypeError:
                continue
        return operaciones

    def pendientes(self) -> list[Operacion]:
        """Operaciones que aún se pueden deshacer, la más reciente primero."""
        return [op for op in reversed(self.todas()) if not op.deshecha]

    def ultima(self) -> Operacion | None:
        pendientes = self.pendientes()
        return pendientes[0] if pendientes else None

    def marcar_deshecha(self, id_operacion: str) -> None:
        """Reescribe el diario marcando una operación como deshecha."""
        operaciones = self.todas()
        for operacion in operaciones:
            if operacion.id == id_operacion:
                operacion.deshecha = True
        lineas = [
            json.dumps(asdict(op), ensure_ascii=False) for op in operaciones
        ]
        self.ruta.write_text(
            ("\n".join(lineas) + "\n") if lineas else "", encoding="utf-8"
        )
