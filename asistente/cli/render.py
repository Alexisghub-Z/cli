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


_ICONOS = {
    "crear": "[green]+[/green]",
    "modificar": "[yellow]~[/yellow]",
    "mover": "[cyan]→[/cyan]",
    "eliminar": "[red]-[/red]",
    "ejecutar": "[magenta]$[/magenta]",
    "leer": "[dim]·[/dim]",
}


def _lineas_vista(vista) -> list[str]:
    """Convierte una vista previa en líneas listas para mostrar."""
    lineas: list[str] = []
    for cambio in vista.cambios:
        icono = _ICONOS.get(cambio.tipo, "·")
        lineas.append(f"{icono} {cambio.detalle}")
        if cambio.aviso:
            lineas.append(f"    [yellow]⚠[/yellow] [italic]{cambio.aviso}[/italic]")
    if not vista.reversible:
        lineas.append("    [red]⚠ Esta acción no se puede deshacer.[/red]")
    return lineas


def pedir_confirmacion(nombre: str, detalle: str, vista=None) -> bool:
    """Pide permiso mostrando la acción exacta y su vista previa."""
    cuerpo = [f"[bold]{nombre}[/bold]", f"[dim]{detalle}[/dim]"]
    if vista is not None:
        cuerpo.append("")
        cuerpo.append("[bold]Esto es lo que pasaría:[/bold]")
        cuerpo.extend(_lineas_vista(vista))

    consola.print(
        Panel(
            "\n".join(cuerpo),
            title="[yellow]Requiere tu permiso[/yellow]",
            border_style="yellow",
        )
    )
    return Confirm.ask("¿Autorizas esta acción?", default=False)


def aprobar_plan(plan, vistas) -> bool:
    """Muestra el plan completo con la vista previa y pide una aprobación."""
    cuerpo: list[str] = []
    if plan.resumen:
        cuerpo.append(f"[bold]{plan.resumen}[/bold]")
        cuerpo.append("")

    for indice, (paso, vista) in enumerate(zip(plan.pasos, vistas), start=1):
        encabezado = f"[bold cyan]{indice}.[/bold cyan] {paso.herramienta}"
        if paso.motivo:
            encabezado += f" [dim]— {paso.motivo}[/dim]"
        cuerpo.append(encabezado)
        if vista is not None:
            cuerpo.extend(f"   {linea}" for linea in _lineas_vista(vista))
        else:
            argumentos = ", ".join(f"{k}={v}" for k, v in paso.argumentos.items())
            cuerpo.append(f"   [dim]· {argumentos}[/dim]")
        cuerpo.append("")

    irreversibles = sum(1 for v in vistas if v is not None and not v.reversible)
    if irreversibles:
        cuerpo.append(
            f"[red]⚠ {irreversibles} paso(s) no se podrán deshacer.[/red]"
        )

    consola.print(
        Panel(
            "\n".join(cuerpo).rstrip(),
            title=f"[cyan]Plan propuesto ({len(plan.pasos)} pasos)[/cyan]",
            border_style="cyan",
        )
    )
    return Confirm.ask("¿Ejecuto este plan?", default=False)


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
    if getattr(ejecucion, "plan", None) is not None and ejecucion.pasos:
        consola.print("[dim]Ejecutando el plan aprobado...[/dim]")
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


# Reexportados para que la CLI no importe Rich directamente.
__all__ = [
    "consola",
    "Confirm",
    "Table",
    "tabla_directorio",
    "pedir_confirmacion",
    "aprobar_plan",
    "aprobar_receta",
    "tabla_recetas",
    "pedir_valor",
    "mostrar_paso",
    "mostrar_ejecucion",
    "error",
    "aviso",
]


def aprobar_receta(receta, preparados) -> bool:
    """Muestra qué hará una receta y pide una sola aprobación."""
    cuerpo: list[str] = []
    if receta.descripcion:
        cuerpo.append(f"[dim]{receta.descripcion}[/dim]")
        cuerpo.append("")

    for indice, paso in enumerate(preparados, start=1):
        cuerpo.append(f"[bold cyan]{indice}.[/bold cyan] {paso.herramienta}")
        if paso.vista is not None:
            cuerpo.extend(f"   {linea}" for linea in _lineas_vista(paso.vista))
        else:
            argumentos = ", ".join(f"{k}={v}" for k, v in paso.argumentos.items())
            cuerpo.append(f"   [dim]· {argumentos}[/dim]")
        cuerpo.append("")

    consola.print(
        Panel(
            "\n".join(cuerpo).rstrip(),
            title=f"[cyan]Receta «{receta.nombre}» ({len(preparados)} pasos)[/cyan]",
            border_style="cyan",
        )
    )
    return Confirm.ask("¿Ejecuto esta receta?", default=False)


def tabla_recetas(recetas) -> "Table":
    """Lista las recetas guardadas."""
    tabla = Table(title="Recetas guardadas")
    tabla.add_column("Nombre", style="cyan", overflow="fold")
    tabla.add_column("Pasos", justify="right", style="dim")
    tabla.add_column("Usos", justify="right", style="dim")
    tabla.add_column("Descripción", overflow="fold")
    for receta in recetas:
        huecos = receta.huecos()
        descripcion = receta.descripcion or "[dim]—[/dim]"
        if huecos:
            descripcion += f" [yellow](pide: {', '.join(huecos)})[/yellow]"
        tabla.add_row(
            receta.nombre, str(len(receta.pasos)), str(receta.veces_usada), descripcion
        )
    return tabla


def pedir_valor(nombre: str) -> str:
    """Pide al usuario el valor de un hueco de la receta."""
    return consola.input(f"[cyan]{nombre}[/cyan]: ").strip()
