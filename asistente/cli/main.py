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


@app.callback(invoke_without_command=True)
def principal(ctx: typer.Context):
    """Sin subcomando, entra al modo interactivo."""
    if ctx.invoked_subcommand is None:
        charlar()


if __name__ == "__main__":
    app()
