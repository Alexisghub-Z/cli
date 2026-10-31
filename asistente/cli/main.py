"""Punto de entrada: modo de un solo comando y modo interactivo (REPL)."""

from __future__ import annotations

import typer

from asistente import config as config_mod
from asistente.agent.loop import Agente
from asistente.cli import render, sesion
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
    return Agente(
        sesion.ClienteVisible(cliente, render.anunciar_herramienta),
        cfg,
        confirmador=render.pedir_confirmacion,
        aprobador_plan=render.aprobar_plan,
    )


def _atender(agente: Agente, peticion: str) -> None:
    """Ejecuta una petición con Bruma animada; nunca deja escapar un traceback.

    Ctrl+C mientras piensa cancela solo esta petición.
    """
    consola = render.consola
    try:
        with render.Pensando():
            ejecucion = agente.ejecutar(peticion)
    except KeyboardInterrupt:
        render.cancelado("Listo, cancelé esa petición.")
        return
    except Exception as exc:  # noqa: BLE001 - el usuario nunca ve tracebacks
        render.error_inesperado(sesion.registrar_error(exc))
        return
    try:
        _recordar(ejecucion)
        render.mostrar_ejecucion(ejecucion, agente.config.modelo)
    except Exception as exc:  # noqa: BLE001
        render.error_inesperado(sesion.registrar_error(exc))
    consola.print()


# Última ejecución de esta sesión, para «asistente receta guardar».
_ultima: "object | None" = None


def _recordar(ejecucion):
    """Guarda la ejecución en memoria y en disco, para poder hacer receta."""
    global _ultima
    _ultima = ejecucion
    if not ejecucion.pasos or ejecucion.abortada:
        return
    try:
        import json

        from asistente.config import cargar as cargar_cfg

        destino = cargar_cfg().ruta_recetas.parent / "ultima.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(
                [
                    {
                        "herramienta": paso.herramienta,
                        "argumentos": paso.argumentos,
                        "ok": paso.resultado.ok,
                        "resumen": paso.resultado.resumen,
                    }
                    for paso in ejecucion.pasos
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass  # no poder recordarla no debe romper la ejecución


@app.command("pedir")
def pedir(peticion: list[str] = typer.Argument(..., help="Qué quieres hacer.")):
    """Ejecuta una sola petición y termina."""
    cfg = config_mod.cargar()
    agente = _crear_agente(cfg)
    estado = sesion.estado_ollama(agente.cliente)
    if estado != "conectado":
        render.sin_ollama(cfg.modelo, estado)
        raise typer.Exit(code=1)
    _atender(agente, " ".join(peticion))


def _deshacer_ultimo() -> None:
    """«deshacer» dentro del modo interactivo: revierte lo último."""
    from asistente.undo.diario import Diario
    from asistente.undo.revertir import revertir

    cfg = config_mod.cargar()
    diario = Diario(cfg.ruta_diario)
    pendientes = diario.pendientes()
    if not pendientes:
        render.aviso("No hay nada que deshacer.")
        return
    operacion = pendientes[0]
    render.consola.print(
        render.Text("Lo último que hice: ").append(operacion.descripcion(), style="bold")
    )
    if not render.preguntar("¿Lo deshago?"):
        render.aviso("Vale, lo dejo como está.")
        return
    ok, mensaje = revertir(operacion, diario)
    if ok:
        render.exito(mensaje)
    else:
        render.problema(mensaje)


@app.command("charlar")
def charlar():
    """Modo interactivo: varias peticiones seguidas."""
    # Ctrl+C fuera de una petición nunca debe acabar en un traceback.
    try:
        _bucle_interactivo()
    except KeyboardInterrupt:
        render.despedida()


def _bucle_interactivo():
    cfg = config_mod.cargar()
    agente = _crear_agente(cfg)
    estado = sesion.estado_ollama(agente.cliente)
    render.bienvenida(cfg.modelo, estado)

    while True:
        render.consola.print()
        render.consola.print(render.linea_comandos())
        try:
            texto = render.consola.input(
                f"[bold {render.AZUL_CLARO}]{render._s('prompt')}[/] "
            )
        except (EOFError, KeyboardInterrupt):
            render.despedida()
            return

        tipo, valor = sesion.resolver_entrada(texto, render.EJEMPLOS)
        if tipo == "sugerir":
            render.sugerir_ejemplo(valor)
            continue
        if tipo == "comando":
            if valor == "salir":
                render.despedida()
                return
            if valor == "ayuda":
                render.ayuda()
            elif valor == "limpiar":
                render.consola.clear()
                render.consola.print(render.linea_estado(cfg.modelo, estado))
            elif valor == "deshacer":
                try:
                    _deshacer_ultimo()
                except Exception as exc:  # noqa: BLE001
                    render.error_inesperado(sesion.registrar_error(exc))
            continue

        if valor != texto.strip():  # eligió un ejemplo por número
            render.consola.print(f"[dim]{render._s('flecha')} {valor}[/dim]")

        # Si Ollama no estaba listo, se vuelve a mirar antes de cada petición.
        if estado != "conectado":
            estado = sesion.estado_ollama(agente.cliente)
            if estado != "conectado":
                render.sin_ollama(cfg.modelo, estado)
                continue
            render.consola.print(render.linea_estado(cfg.modelo, estado))

        _atender(agente, valor)


@app.command("herramientas")
def herramientas():
    """Lista las herramientas disponibles y su nivel de permiso."""
    from asistente.tools import registro

    cargar_herramientas()
    tabla = render.Table(title="Herramientas disponibles")
    tabla.add_column("Nombre", style=render.AZUL_CLARO)
    tabla.add_column("Permiso", style=render.AMARILLO)
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
        render.exito(f"Configuración en: {ruta}")
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
            render.exito(f"{mensaje}")
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


recetas_app = typer.Typer(help="Guarda tareas que salieron bien y repítelas.")
app.add_typer(recetas_app, name="receta")


def _pasos_recordados():
    """Recupera los pasos de la última ejecución (memoria o disco)."""
    if _ultima is not None and getattr(_ultima, "pasos", None):
        return _ultima.pasos

    import json
    from dataclasses import dataclass

    from asistente.tools.base import Resultado

    @dataclass
    class _Paso:
        herramienta: str
        argumentos: dict
        resultado: Resultado

    ruta = config_mod.cargar().ruta_recetas.parent / "ultima.json"
    if not ruta.is_file():
        return []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [
        _Paso(
            herramienta=str(d.get("herramienta", "")),
            argumentos=d.get("argumentos") or {},
            resultado=Resultado(
                ok=bool(d.get("ok")), resumen=str(d.get("resumen") or "")
            ),
        )
        for d in datos
        if isinstance(d, dict)
    ]


@recetas_app.command("guardar")
def receta_guardar(
    nombre: str = typer.Argument(..., help="Nombre de la receta."),
    descripcion: str = typer.Option("", "--descripcion", help="Para qué sirve."),
):
    """Guarda la última tarea realizada como receta reutilizable."""
    from asistente.recetas import modelo

    valido, motivo = modelo.nombre_valido(nombre)
    if not valido:
        render.error(motivo)
        raise typer.Exit(code=1)

    pasos = _pasos_recordados()
    if not pasos:
        render.aviso(
            "No hay ninguna tarea reciente que guardar. Pide algo primero, "
            "por ejemplo: asistente pedir \"crea una carpeta Facturas\""
        )
        raise typer.Exit(code=1)

    receta, problema = modelo.desde_pasos(nombre, pasos, descripcion)
    if receta is None:
        render.error(problema)
        raise typer.Exit(code=1)

    cfg = config_mod.cargar()
    existente = modelo.buscar(nombre, cfg.ruta_recetas)
    if existente is not None and not render.Confirm.ask(
        f"Ya existe una receta «{existente.nombre}». ¿La reemplazo?", default=False
    ):
        render.aviso("Cancelado.")
        return

    ruta = modelo.guardar(receta, cfg.ruta_recetas)
    render.exito(
        f"Receta «{receta.nombre}» guardada "
        f"({len(receta.pasos)} pasos)."
    )
    huecos = receta.huecos()
    if huecos:
        render.consola.print(
            f"[dim]Pedirá estos datos al ejecutarla: {', '.join(huecos)}[/dim]"
        )
    render.consola.print(f"[dim]{ruta}[/dim]")


@recetas_app.command("listar")
def receta_listar():
    """Muestra las recetas guardadas."""
    from asistente.recetas import modelo

    recetas = modelo.todas(config_mod.cargar().ruta_recetas)
    if not recetas:
        render.consola.print(
            "[dim]No hay recetas guardadas. Haz una tarea y luego:[/dim]\n"
            '[dim]  asistente receta guardar "mi tarea"[/dim]'
        )
        return
    render.consola.print(render.tabla_recetas(recetas))


@recetas_app.command("ejecutar")
def receta_ejecutar(
    nombre: str = typer.Argument(..., help="Nombre de la receta."),
    dato: list[str] = typer.Option(
        None, "--dato", help="Valor de un hueco, como carpeta=~/Descargas."
    ),
):
    """Reproduce una receta guardada."""
    from asistente.recetas import ejecutor, modelo

    cfg = config_mod.cargar()
    receta = modelo.buscar(nombre, cfg.ruta_recetas)
    if receta is None:
        render.error(
            f"No encuentro la receta «{nombre}». "
            "Usa «asistente receta listar» para ver las que hay."
        )
        raise typer.Exit(code=1)

    valores: dict[str, str] = {}
    for crudo in dato or []:
        if "=" in crudo:
            clave, _, valor = crudo.partition("=")
            valores[clave.strip()] = valor.strip()

    # Lo que falte, se pregunta.
    for hueco in receta.huecos():
        if not valores.get(hueco):
            valores[hueco] = render.pedir_valor(hueco)
            if not valores[hueco]:
                render.aviso("Cancelado: hace falta ese dato.")
                raise typer.Exit(code=1)

    cargar_herramientas()
    agente = Agente(_ClienteNulo(), cfg)
    preparados, problema = ejecutor.preparar(receta, valores, agente._autorizar)
    if problema:
        render.error(problema)
        raise typer.Exit(code=1)

    if not render.aprobar_receta(receta, preparados):
        render.aviso("Cancelado.")
        return

    resultado = ejecutor.ejecutar(preparados)
    for herramienta, salida in resultado.pasos:
        if salida.ok:
            render.exito(f"{salida.resumen}")
        else:
            render.error(salida.resumen)

    if resultado.abortada:
        render.error(resultado.motivo)
        return

    receta.veces_usada += 1
    modelo.guardar(receta, cfg.ruta_recetas)
    render.exito(
        f"Receta «{receta.nombre}» completada "
        f"({len(resultado.pasos)} pasos)."
    )


@recetas_app.command("borrar")
def receta_borrar(nombre: str = typer.Argument(..., help="Nombre de la receta.")):
    """Elimina una receta guardada."""
    from asistente.recetas import modelo

    cfg = config_mod.cargar()
    receta = modelo.buscar(nombre, cfg.ruta_recetas)
    if receta is None:
        render.error(f"No encuentro la receta «{nombre}».")
        raise typer.Exit(code=1)

    if not render.Confirm.ask(
        f"¿Borro la receta «{receta.nombre}»?", default=False
    ):
        render.aviso("Cancelado.")
        return

    (cfg.ruta_recetas / modelo.archivo_de(receta.nombre)).unlink(missing_ok=True)
    render.exito(f"Receta «{receta.nombre}» borrada.")


class _ClienteNulo:
    """Cliente vacío: ejecutar una receta no necesita el modelo."""

    def responder(self, mensajes, herramientas=None):
        from asistente.llm.base import RespuestaModelo

        return RespuestaModelo(texto="")

    def disponible(self):
        return True, ""


@app.callback(invoke_without_command=True)
def principal(ctx: typer.Context):
    """Sin subcomando, entra al modo interactivo."""
    if ctx.invoked_subcommand is None:
        charlar()


if __name__ == "__main__":
    app()
