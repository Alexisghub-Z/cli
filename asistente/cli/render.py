"""Presentación en terminal con Rich (aislada para poder probar la lógica)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

consola = Console()


def tabla_directorio(datos: dict) -> Table:
    """Tabla con el contenido de una carpeta."""
    tabla = Table(title=f"Contenido de {datos.get('ruta', '')}", show_lines=False)
    tabla.add_column("Tipo", style="cyan", width=10, no_wrap=True)
    tabla.add_column("Nombre", style="white", overflow="fold")
    tabla.add_column("Tamaño", justify="right", style="dim")

    for item in datos.get("items", []):
        icono = "📁" if item["tipo"] == "carpeta" else "📄"
        tabla.add_row(icono, item["nombre"], item["tamano_legible"])
    return tabla


def pedir_confirmacion(nombre: str, detalle: str) -> bool:
    """Pide permiso al usuario mostrando la acción exacta."""
    consola.print(
        Panel(
            f"[bold]{nombre}[/bold]\n[dim]{detalle}[/dim]",
            title="[yellow]Requiere tu permiso[/yellow]",
            border_style="yellow",
        )
    )
    return Confirm.ask("¿Autorizas esta acción?", default=False)


def mostrar_paso(paso) -> None:
    """Muestra el resultado de un paso ejecutado."""
    if not paso.resultado.ok:
        consola.print(f"[red]✗[/red] {paso.resultado.resumen}")
        return

    consola.print(f"[green]✓[/green] [dim]{paso.herramienta}[/dim]")
    if paso.herramienta == "listar_directorio" and paso.resultado.datos:
        consola.print(tabla_directorio(paso.resultado.datos))
    else:
        consola.print(f"  {paso.resultado.resumen}")


def mostrar_ejecucion(ejecucion) -> None:
    """Muestra el resultado completo de una petición."""
    for paso in ejecucion.pasos:
        mostrar_paso(paso)

    if ejecucion.abortada:
        consola.print(
            Panel(
                ejecucion.motivo_aborto,
                title="[red]Detenido[/red]",
                border_style="red",
            )
        )
    elif ejecucion.respuesta:
        consola.print(Panel(ejecucion.respuesta, border_style="green"))


def error(mensaje: str) -> None:
    consola.print(f"[bold red]Error:[/bold red] {mensaje}")


def aviso(mensaje: str) -> None:
    consola.print(f"[yellow]![/yellow] {mensaje}")
