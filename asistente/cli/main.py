"""Punto de entrada: modo de un solo comando y modo interactivo (REPL)."""

from __future__ import annotations

import typer

from asistente import config as config_mod
from asistente.agent.loop import Agente
from asistente.cli import render
from asistente.llm.ollama import ClienteOllama
from asistente.tools import cargar_herramientas

app = typer.Typer(
    help="Asistente de terminal con IA local, en español.",
    no_args_is_help=False,
    add_completion=False,
)


def _crear_agente(cfg: config_mod.Config) -> Agente:
    cargar_herramientas()
    cliente = ClienteOllama(
        modelo=cfg.modelo,
        host=cfg.host,
        temperatura=cfg.temperatura,
        tiempo_limite=cfg.tiempo_limite,
    )
    return Agente(cliente, cfg, confirmador=render.pedir_confirmacion)


def _comprobar_modelo(agente: Agente) -> bool:
    disponible, motivo = agente.cliente.disponible()
    if not disponible:
        render.error(motivo)
        render.aviso(
            "Instala Ollama desde https://ollama.com y luego ejecuta:\n"
            f"  ollama pull {agente.config.modelo}"
        )
    return disponible


@app.command("pedir")
def pedir(peticion: list[str] = typer.Argument(..., help="Qué quieres hacer.")):
    """Ejecuta una sola petición y termina."""
    cfg = config_mod.cargar()
    agente = _crear_agente(cfg)
    if not _comprobar_modelo(agente):
        raise typer.Exit(code=1)

    render.mostrar_ejecucion(agente.ejecutar(" ".join(peticion)))


@app.command("charlar")
def charlar():
    """Modo interactivo: varias peticiones seguidas."""
    cfg = config_mod.cargar()
    agente = _crear_agente(cfg)
    if not _comprobar_modelo(agente):
        raise typer.Exit(code=1)

    render.consola.print(
        f"[bold green]Asistente[/bold green] "
        f"[dim]({cfg.modelo})[/dim] — escribe 'salir' para terminar."
    )
    while True:
        try:
            peticion = render.consola.input("[bold cyan]›[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            render.consola.print("\n[dim]Hasta luego.[/dim]")
            return
        if peticion.lower() in {"salir", "exit", "quit", ""}:
            render.consola.print("[dim]Hasta luego.[/dim]")
            return
        render.mostrar_ejecucion(agente.ejecutar(peticion))


@app.command("herramientas")
def herramientas():
    """Lista las herramientas disponibles y su nivel de permiso."""
    from asistente.tools import registro

    cargar_herramientas()
    tabla = render.Table(title="Herramientas disponibles")
    tabla.add_column("Nombre", style="cyan")
    tabla.add_column("Permiso", style="yellow")
    tabla.add_column("Descripción", overflow="fold")

    for nombre, clase in sorted(registro.todas().items()):
        tabla.add_row(nombre, clase.nivel.value, clase.descripcion)
    render.consola.print(tabla)


@app.command("config")
def configurar(
    mostrar: bool = typer.Option(False, "--mostrar", help="Muestra la config."),
    crear: bool = typer.Option(False, "--crear", help="Crea el archivo."),
):
    """Muestra o crea el archivo de configuración."""
    cfg = config_mod.cargar()
    if crear:
        ruta = config_mod.guardar(cfg)
        render.consola.print(f"[green]✓[/green] Configuración en: {ruta}")
        return

    render.consola.print(f"[dim]Archivo:[/dim] {config_mod.ruta_archivo_config()}")
    for campo in cfg.__dataclass_fields__:
        render.consola.print(f"  {campo} = {getattr(cfg, campo)}")


@app.command("deshacer")
def deshacer(
    todo: bool = typer.Option(
        False, "--todo", help="Deshace todas las operaciones pendientes."
    ),
    listar: bool = typer.Option(
        False, "--listar", help="Solo muestra lo que se puede deshacer."
    ),
):
    """Revierte la última operación (o todas con --todo)."""
    from asistente.undo.diario import Diario
    from asistente.undo.revertir import revertir

    cfg = config_mod.cargar()
    diario = Diario(cfg.ruta_diario)
    pendientes = diario.pendientes()

    if not pendientes:
        render.aviso("No hay nada que deshacer.")
        return

    if listar:
        tabla = render.Table(title="Operaciones que puedo deshacer")
        tabla.add_column("#", style="dim", width=3)
        tabla.add_column("Operación", overflow="fold")
        for indice, operacion in enumerate(pendientes, start=1):
            tabla.add_row(str(indice), operacion.descripcion())
        render.consola.print(tabla)
        return

    objetivo = pendientes if todo else pendientes[:1]
    for operacion in objetivo:
        render.consola.print(f"[dim]{operacion.descripcion()}[/dim]")
        if not render.Confirm.ask("¿Deshago esta operación?", default=True):
            render.aviso("Cancelado.")
            return
        ok, mensaje = revertir(operacion, diario)
        if ok:
            render.consola.print(f"[green]✓[/green] {mensaje}")
        else:
            render.error(mensaje)


@app.command("papelera")
def papelera():
    """Muestra qué hay en la papelera del asistente."""
    cfg = config_mod.cargar()
    carpeta = cfg.ruta_papelera

    if not carpeta.exists() or not any(carpeta.iterdir()):
        render.consola.print("[dim]La papelera está vacía.[/dim]")
        return

    from asistente.tools.listar import formato_tamano

    tabla = render.Table(title=f"Papelera ({carpeta})")
    tabla.add_column("Archivo", overflow="fold")
    tabla.add_column("Tamaño", justify="right", style="dim")
    total = 0
    for elemento in sorted(carpeta.iterdir()):
        try:
            tamano = elemento.stat().st_size
        except OSError:
            tamano = 0
        total += tamano
        tabla.add_row(elemento.name, formato_tamano(tamano))
    render.consola.print(tabla)
    render.consola.print(f"[dim]Total: {formato_tamano(total)}[/dim]")


@app.callback(invoke_without_command=True)
def principal(ctx: typer.Context):
    """Sin subcomando, entra al modo interactivo."""
    if ctx.invoked_subcommand is None:
        charlar()


if __name__ == "__main__":
    app()
