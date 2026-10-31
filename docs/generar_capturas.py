"""Genera docs/capturas.md: cada pantalla de la interfaz en texto plano.

Uso:  python docs/generar_capturas.py

No necesita Ollama ni una terminal real: pinta cada pantalla en una
`Console(record=True)` con datos de ejemplo y guarda el texto exportado.
"""

from __future__ import annotations

import builtins
import io
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from asistente.agent.planner import PasoPlan, Plan
from asistente.agent.vista_previa import Cambio, VistaPrevia
from asistente.cli import render
from asistente.cli.mascota import ESTADOS, mascota
from asistente.tools.base import Resultado

DESTINO = Path(__file__).with_name("capturas.md")
CASA = str(Path.home())


class _TerminalASCII(io.StringIO):
    """Simula una terminal sin Unicode (como cmd.exe antiguo)."""

    encoding = "ascii"


def _consola(ancho: int = 80, simple: bool = False) -> Console:
    return Console(
        record=True,
        width=ancho,
        file=_TerminalASCII() if simple else io.StringIO(),
        force_terminal=not simple,
        color_system=None if simple else "truecolor",
        legacy_windows=False,
    )


def capturar(titulo: str, pintar, ancho: int = 80, simple: bool = False,
             respuesta: str = "") -> str:
    render.consola = _consola(ancho, simple)
    original = builtins.input
    def _escribir(*_):  # lo que «teclea» el usuario
        render.consola.print(respuesta, highlight=False)
        return respuesta

    builtins.input = _escribir
    try:
        pintar()
    finally:
        builtins.input = original
    texto = render.consola.export_text().rstrip()
    return f"## {titulo}\n\n```text\n{texto}\n```\n"


def _archivos() -> dict:
    nombres = [
        ("ubuntu-24.04-desktop.iso", 6_100_000_000, 40),
        ("Proyecto final (video).mp4", 1_830_000_000, 3),
        ("fotos-vacaciones.zip", 942_000_000, 12),
        ("instalador-zoom.pkg", 312_000_000, 1),
        ("Presentación hackathon.pptx", 48_500_000, 0),
    ] + [(f"factura-{n:02d}.pdf", 210_000 + n * 1000, n) for n in range(1, 18)]
    items = [
        {
            "ruta": "",
            "nombre": nombre,
            "tamano": tamano,
            "tamano_legible": _legible(tamano),
            "dias": dias,
        }
        for nombre, tamano, dias in nombres
    ]
    return {"ruta": f"{CASA}/Downloads", "total": len(items), "items": items}


def _legible(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024
    return f"{n:.1f} TB"


def pantalla_bienvenida():
    render.bienvenida("qwen3:8b", "conectado")
    render.consola.print()
    render.consola.print(render.linea_comandos())
    render.consola.print(f"[bold {render.AZUL_CLARO}]{render._s('prompt')}[/] ")


def pantalla_pensando():
    render.consola.print("[dim]→ ¿Qué archivos pesan más en Descargas?[/dim]")
    render.anunciar_herramienta("buscar_archivos", {"ruta": "~/Downloads"})
    render.consola.print(render.Pensando().fotograma(7.2))


def pantalla_resultado():
    paso = SimpleNamespace(
        herramienta="buscar_archivos",
        argumentos={"ruta": "~/Downloads"},
        resultado=Resultado(
            ok=True,
            resumen=f"22 archivos en {CASA}/Downloads (9.6 GB en total)",
            datos=_archivos(),
        ),
    )
    ejecucion = SimpleNamespace(
        pasos=[paso],
        abortada=False,
        motivo_aborto="",
        respuesta=(
            "Lo que más pesa en Descargas es la imagen de Ubuntu (5.7 GB) y "
            "el video del proyecto (1.7 GB). Si ya no los usas, puedo "
            "mandarlos a la papelera."
        ),
    )
    render.mostrar_ejecucion(ejecucion, "qwen3:8b")


def pantalla_confirmacion():
    plan = Plan(
        resumen="Ordenar Descargas en carpetas por tipo",
        pasos=[
            PasoPlan("crear_carpeta", {"ruta": "~/Downloads/PDF"}),
            PasoPlan("mover", {"origen": "~/Downloads/factura-01.pdf",
                               "destino": "~/Downloads/PDF/"}),
            PasoPlan("enviar_a_papelera", {"ruta": "~/Downloads/instalador-zoom.pkg"}),
        ],
    )
    vistas = [
        VistaPrevia("Crear carpeta", [Cambio("crear", "Carpeta nueva: ~/Downloads/PDF")]),
        VistaPrevia("Mover", [Cambio("mover", "factura-01.pdf a ~/Downloads/PDF/")]),
        VistaPrevia(
            "Papelera",
            [Cambio("eliminar", "instalador-zoom.pkg (312 MB) a la papelera",
                    aviso="Lo puedes recuperar con «deshacer».")],
        ),
    ]
    aprobado = render.aprobar_plan(plan, vistas)
    if not aprobado:
        render.cancelado("De acuerdo, no toqué nada.")


def pantalla_error():
    ejecucion = SimpleNamespace(
        pasos=[],
        abortada=True,
        motivo_aborto=(
            "No puedo modificar «/etc/hosts»: pertenece al sistema operativo."
        ),
        respuesta="",
    )
    render.mostrar_ejecucion(ejecucion, "qwen3:8b")


def pantalla_sin_ollama():
    render.bienvenida("qwen3:8b", "sin_conexion")


def pantalla_sin_sentido():
    render.sugerir_ejemplo("asdfghjkl")


def pantalla_despedida():
    render.despedida()


def expresiones(simple: bool) -> str:
    consola = _consola(80, simple)
    for estado in ESTADOS:
        consola.print(f"{estado}:")
        consola.print(mascota(estado, ascii=simple))
        consola.print()
    return consola.export_text().rstrip()


def main() -> None:
    partes = [
        "# Capturas de la interfaz\n",
        "Generadas con `python docs/generar_capturas.py` "
        "(`Console(record=True).export_text()`), sin Ollama ni terminal real. "
        "El texto plano pierde los colores: en la terminal Bruma tiene el "
        "cuerpo azul marino, el contorno azul claro y los ojos blancos.\n",
        "## Bruma: las cinco expresiones\n\n```text\n" + expresiones(False) + "\n```\n",
        "## Bruma en modo ASCII (terminal sin Unicode o con NO_COLOR)\n\n```text\n"
        + expresiones(True) + "\n```\n",
        capturar("Bienvenida", pantalla_bienvenida),
        capturar("Pensando (un fotograma de la animación)", pantalla_pensando),
        capturar("Resultado con tabla (más de 15 filas)", pantalla_resultado),
        capturar("Confirmación de un plan (respondiendo «n»)", pantalla_confirmacion, respuesta="n"),
        capturar("Error", pantalla_error),
        capturar("Sin Ollama", pantalla_sin_ollama),
        capturar("Entrada sin sentido", pantalla_sin_sentido),
        capturar("Despedida", pantalla_despedida),
        capturar("Bienvenida en modo ASCII", pantalla_bienvenida, simple=True),
        capturar("Terminal angosta (menos de 60 columnas)", pantalla_error, ancho=50),
    ]
    DESTINO.write_text("\n".join(partes), encoding="utf-8")
    print(f"Capturas guardadas en {DESTINO}")


if __name__ == "__main__":
    main()
