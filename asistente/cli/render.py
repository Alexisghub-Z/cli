"""Presentación en terminal con Rich (aislada para poder probar la lógica).

Todas las pantallas leen la consola del módulo (`consola`) en el momento de
pintar, así las pruebas pueden cambiarla por una `Console(record=True)`.
"""

from __future__ import annotations

import time
import unicodedata
from datetime import datetime
from pathlib import Path

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from asistente.cli import estilo
from asistente.cli.estilo import AMARILLO, AZUL_CLARO, ROJO, VERDE
from asistente.cli.mascota import mascota

consola = Console(highlight=False)

EJEMPLOS = (
    "¿Qué archivos pesan más en Descargas?",
    "Ordena mi carpeta de Descargas por tipo",
    "¿Cuánto espacio libre tengo?",
    "Busca los PDF de esta semana",
    "Comprime mi carpeta de Documentos",
)

COMANDOS = ("ayuda", "deshacer", "limpiar", "salir")

MAX_FILAS = 15


# --- utilidades -------------------------------------------------------------


def _simple() -> bool:
    return estilo.modo_simple(consola)


def _s(nombre: str) -> str:
    return estilo.simbolo(nombre, _simple())


def con_mascota(estado: str, contenido: RenderableType) -> RenderableType:
    """Pone a Bruma a la izquierda del contenido (si cabe)."""
    if not estilo.cabe_mascota(consola):
        return contenido
    rejilla = Table.grid(padding=(0, 2))
    rejilla.add_column(no_wrap=True, vertical="middle")
    rejilla.add_column(ratio=1, vertical="middle")
    rejilla.add_row(mascota(estado, ascii=_simple()), contenido)
    return rejilla


def bonita(ruta: str) -> str:
    """Ruta corta y legible: la carpeta personal se muestra como «~»."""
    if not ruta:
        return ""
    try:
        completa = Path(ruta).expanduser()
        casa = Path.home()
        if completa == casa:
            return "~"
        return "~/" + str(completa.relative_to(casa))
    except ValueError:
        return ruta


def _lugar(ruta: str) -> str:
    """Nombre corto de una carpeta para frases como «Buscando en Descargas»."""
    if ruta in {"", "~"}:
        return "tu carpeta personal"
    if ruta == ".":
        return "esta carpeta"
    return Path(ruta).expanduser().name or ruta


_MESES = ("ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic")


def fecha_legible(momento: float, ahora: float | None = None) -> str:
    """«hoy», «ayer», «hace 3 días» o «12 oct 2026»."""
    ahora = time.time() if ahora is None else ahora
    dia = datetime.fromtimestamp(momento).date()
    hoy = datetime.fromtimestamp(ahora).date()
    dias = (hoy - dia).days
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    if dias < 7:
        return f"hace {dias} días"
    return f"{dia.day} {_MESES[dia.month - 1]} {dia.year}"


# --- herramientas en lenguaje sencillo --------------------------------------

# nombre: (emoji, qué es en el plan, cómo se anuncia mientras corre)
_ACCIONES = {
    "listar_directorio": ("📂", "Ver lo que hay en una carpeta", "Mirando {lugar}"),
    "buscar_archivos": ("🔍", "Buscar archivos", "Buscando en {lugar}"),
    "leer_archivo": ("📖", "Leer un archivo", "Leyendo {lugar}"),
    "info_archivo": ("🔎", "Ver los detalles de un archivo", "Revisando {lugar}"),
    "espacio_en_disco": ("💽", "Medir el espacio libre", "Midiendo el espacio libre"),
    "procesos": ("📊", "Ver los programas abiertos", "Revisando los programas abiertos"),
    "comprimir": ("📦", "Comprimir", "Comprimiendo {lugar}"),
    "descomprimir": ("📦", "Descomprimir", "Descomprimiendo {lugar}"),
    "mover": ("🚚", "Mover", "Moviendo {lugar}"),
    "copiar": ("📋", "Copiar", "Copiando {lugar}"),
    "renombrar": ("📝", "Cambiar el nombre", "Renombrando {lugar}"),
    "crear_carpeta": ("📁", "Crear una carpeta", "Creando {lugar}"),
    "enviar_a_papelera": ("🧹", "Mandar a la papelera", "Mandando {lugar} a la papelera"),
    "ejecutar_comando": ("💻", "Ejecutar un comando", "Ejecutando un comando"),
}


def etiqueta(herramienta: str) -> str:
    """Nombre de la herramienta en palabras sencillas."""
    accion = _ACCIONES.get(herramienta)
    return accion[1] if accion else herramienta.replace("_", " ").capitalize()


def frase_herramienta(herramienta: str, argumentos: dict) -> str:
    """«🔍 Buscando en Descargas...» (o «> Buscando...» en modo ASCII)."""
    emoji, _, plantilla = _ACCIONES.get(
        herramienta, ("⚙", "", herramienta.replace("_", " ").capitalize())
    )
    ruta = str(
        argumentos.get("ruta")
        or argumentos.get("origen")
        or argumentos.get("archivo")
        or ""
    )
    texto = plantilla.format(lugar=_lugar(ruta)) + "..."
    return f"{'>' if _simple() else emoji} {texto}"


def anunciar_herramienta(herramienta: str, argumentos: dict) -> None:
    """Muestra qué está haciendo el asistente (encima de la animación)."""
    linea = Text(frase_herramienta(herramienta, argumentos), style=AZUL_CLARO)
    if _animacion is not None and _animacion.activa:
        _animacion.live.console.print(linea)
    else:
        consola.print(linea)


# --- bienvenida, ayuda y despedida ------------------------------------------


def panel_ejemplos() -> Panel:
    cuerpo = Text()
    for numero, ejemplo in enumerate(EJEMPLOS, start=1):
        cuerpo.append(f" {numero}  ", style=f"bold {AZUL_CLARO}")
        cuerpo.append(ejemplo + "\n")
    cuerpo.append("\nEscribe el número o pídemelo con tus palabras.", style="dim")
    return Panel(
        cuerpo,
        title="Puedes pedirme, por ejemplo",
        title_align="left",
        border_style=AZUL_CLARO,
        padding=(1, 2),
    )


def linea_estado(modelo: str, estado_ollama: str) -> Text:
    """«qwen3:8b · ● conectado» en una línea discreta."""
    texto = Text(f"{modelo}  {_s('separador')}  ", style="dim")
    punto = _s("punto")
    if estado_ollama == "conectado":
        texto.append(f"{punto} conectado", style=VERDE)
    elif estado_ollama == "sin_modelo":
        texto.append(f"{punto} falta el modelo", style=AMARILLO)
    else:
        texto.append(f"{punto} sin conexión", style=ROJO)
    return texto


def linea_comandos() -> Text:
    sep = f"  {_s('separador')}  "
    return Text(sep.join(COMANDOS), style="dim")


def bienvenida(modelo: str, estado_ollama: str) -> None:
    consola.print()
    if estado_ollama == "conectado":
        saludo = Text("¡Hola! Soy Bruma, te ayudo con tus archivos.", style="bold")
        consola.print(con_mascota("normal", saludo))
        consola.print()
        consola.print(panel_ejemplos())
    else:
        sin_ollama(modelo, estado_ollama)
    consola.print(linea_estado(modelo, estado_ollama))


def ayuda() -> None:
    consola.print()
    consola.print(panel_ejemplos())
    consola.print(
        Text("También entiendo: ", style="dim").append(linea_comandos())
    )


def despedida() -> None:
    consola.print()
    consola.print(
        con_mascota("feliz", Text("¡Hasta luego! Aquí estaré cuando me necesites."))
    )
    consola.print()


def sugerir_ejemplo(texto: str = "") -> None:
    """Respuesta a una entrada vacía o sin sentido: propone un ejemplo."""
    ejemplo = EJEMPLOS[len(texto) % len(EJEMPLOS)]
    mensaje = Text()
    if texto:
        mensaje.append("Mmm, no te entendí. ", style="bold")
    mensaje.append("Prueba con algo como:\n")
    mensaje.append(f"«{ejemplo}»", style=AZUL_CLARO)
    mensaje.append("\n\nO escribe un número del 1 al 5.", style="dim")
    consola.print(con_mascota("preguntando", mensaje))


# --- Ollama sin conexión ----------------------------------------------------


def sin_ollama(modelo: str, estado_ollama: str = "sin_conexion") -> None:
    """Explica en pocos pasos cómo poner en marcha el modelo."""
    if estado_ollama == "sin_modelo":
        problema = f"Ollama está abierto, pero falta el modelo {modelo}."
        pasos = [
            ("Abre otra terminal y escribe:", f"ollama pull {modelo}"),
            ("Espera a que termine la descarga (son unos GB).", ""),
            ("Vuelve aquí y pídeme algo.", ""),
        ]
    else:
        problema = "No puedo hablar con Ollama, que es mi cerebro."
        pasos = [
            ("Abre la app de Ollama, o en otra terminal escribe:", "ollama serve"),
            ("Si es la primera vez, descarga el modelo:", f"ollama pull {modelo}"),
            ("Vuelve aquí y pídeme algo: lo intento de nuevo.", ""),
        ]

    cuerpo = Text()
    for numero, (paso, comando) in enumerate(pasos, start=1):
        cuerpo.append(f"{numero}. ", style=f"bold {AZUL_CLARO}")
        cuerpo.append(paso)
        if comando:
            cuerpo.append(f"\n   {comando}", style="bold")
        cuerpo.append("\n")
    cuerpo.rstrip()
    consola.print(con_mascota("preocupado", Text(problema, style="bold")))
    consola.print()
    consola.print(
        Panel(
            cuerpo,
            title="Cómo arreglarlo",
            title_align="left",
            border_style=AMARILLO,
            padding=(1, 2),
        )
    )


# --- animación mientras piensa ----------------------------------------------


class Pensando:
    """Bruma pensando, con «Pensando...» y el tiempo transcurrido.

    Se usa como `with Pensando():`. La animación es suave a propósito:
    los puntos avanzan dos veces por segundo y Bruma parpadea una vez
    cada pocos segundos.
    """

    PARPADEO_CADA = 4.0  # segundos
    PARPADEO_DURA = 0.25

    def __init__(self, texto: str = "Pensando") -> None:
        self.texto = texto
        self.inicio = time.monotonic()
        self.live: Live | None = None
        self.activa = False

    def fotograma(self, transcurrido: float) -> RenderableType:
        puntos = int(transcurrido * 2) % 4
        parpadeo = transcurrido % self.PARPADEO_CADA > (
            self.PARPADEO_CADA - self.PARPADEO_DURA
        )
        estado = Text()
        estado.append(self.texto + "." * puntos + " " * (3 - puntos), style="bold")
        estado.append(f"  {int(transcurrido)} s", style="dim")
        estado.append("\nCtrl+C para cancelar", style="dim")
        if not estilo.cabe_mascota(consola):
            return estado
        rejilla = Table.grid(padding=(0, 2))
        rejilla.add_column(no_wrap=True, vertical="middle")
        rejilla.add_column(vertical="middle")
        rejilla.add_row(
            mascota("pensando", ascii=_simple(), parpadeo=parpadeo, puntos=puntos),
            estado,
        )
        return rejilla

    def __rich__(self) -> RenderableType:
        return self.fotograma(time.monotonic() - self.inicio)

    def __enter__(self) -> "Pensando":
        global _animacion
        _animacion = self
        self.reanudar()
        return self

    def __exit__(self, *exc) -> None:
        global _animacion
        self.pausar()
        _animacion = None

    def pausar(self) -> None:
        if self.live is not None and self.activa:
            self.live.stop()
        self.activa = False

    def reanudar(self) -> None:
        if self.activa:
            return
        self.live = Live(
            self,
            console=consola,
            refresh_per_second=4,
            transient=True,
        )
        self.live.start()
        self.activa = True


_animacion: Pensando | None = None


class _SinAnimacion:
    """Detiene la animación mientras se le pregunta algo al usuario."""

    def __enter__(self):
        self.pausada = _animacion is not None and _animacion.activa
        if self.pausada:
            _animacion.pausar()

    def __exit__(self, *exc):
        if self.pausada and _animacion is not None:
            _animacion.reanudar()


# --- preguntas sí/no --------------------------------------------------------

_SI = {"s", "si", "sí", "y", "yes"}


def interpretar_respuesta(texto: str) -> bool:
    """True solo para s, si, sí, y, yes. Cualquier otra cosa es «no»."""
    limpio = unicodedata.normalize("NFC", texto or "").strip().lower()
    limpio = limpio.strip(".!¡ ")
    return limpio in _SI


def preguntar(pregunta: str = "¿Lo hago?") -> bool:
    """Pregunta sí/no con «no» por defecto. Ctrl+C también es «no»."""
    try:
        respuesta = consola.input(
            f"[bold]{pregunta}[/bold] [dim]\\[s/N][/dim] "
        )
    except (EOFError, KeyboardInterrupt):
        consola.print()
        return False
    return interpretar_respuesta(respuesta)


# --- confirmaciones ---------------------------------------------------------

_ICONOS = {
    "crear": ("+", VERDE),
    "modificar": ("~", AMARILLO),
    "mover": ("→", AZUL_CLARO),
    "eliminar": ("-", ROJO),
    "ejecutar": ("$", AZUL_CLARO),
    "leer": ("·", "dim"),
}


def _lineas_vista(vista, sangria: str = "") -> Text:
    """Convierte una vista previa en líneas listas para mostrar."""
    texto = Text()
    for cambio in vista.cambios:
        icono, color = _ICONOS.get(cambio.tipo, ("·", "dim"))
        if _simple() and icono in {"→", "·"}:
            icono = {"→": ">", "·": "."}[icono]
        texto.append(f"{sangria}{icono} ", style=color)
        texto.append(cambio.detalle + "\n")
        if cambio.aviso:
            texto.append(f"{sangria}  {_s('aviso')} {cambio.aviso}\n", style=AMARILLO)
    if not vista.reversible:
        texto.append(
            f"{sangria}{_s('aviso')} Esto no se puede deshacer.\n", style=AMARILLO
        )
    return texto


def _argumentos_legibles(argumentos: dict, sangria: str = "") -> Text:
    texto = Text(style="dim")
    for clave, valor in argumentos.items():
        valor = bonita(valor) if isinstance(valor, str) and "/" in valor else valor
        texto.append(f"{sangria}{clave.replace('_', ' ')}: {valor}\n")
    return texto


def _panel_permiso(cuerpo: Text, titulo: str) -> RenderableType:
    cuerpo.rstrip()
    panel = Panel(
        cuerpo,
        title=titulo,
        title_align="left",
        border_style=AZUL_CLARO,
        padding=(1, 2),
    )
    return con_mascota("preguntando", panel)


def _detalle_a_dict(detalle: str) -> dict:
    """«ruta=/x, nombre=y» → {"ruta": "/x", "nombre": "y"}."""
    resultado: dict = {}
    for trozo in detalle.split(", "):
        clave, sep, valor = trozo.partition("=")
        if sep:
            resultado[clave.strip()] = valor.strip()
    return resultado


def pedir_confirmacion(nombre: str, detalle: str, vista=None) -> bool:
    """Pide permiso mostrando en palabras sencillas lo que va a pasar."""
    with _SinAnimacion():
        cuerpo = Text(etiqueta(nombre) + "\n\n", style="bold")
        if vista is not None and vista.cambios:
            cuerpo.append_text(_lineas_vista(vista))
        else:
            cuerpo.append_text(_argumentos_legibles(_detalle_a_dict(detalle)))
        consola.print()
        consola.print(_panel_permiso(cuerpo, "Necesito tu permiso"))
        return preguntar("¿Lo hago?")


def aprobar_plan(plan, vistas) -> bool:
    """Muestra el plan completo con la vista previa y pide una aprobación."""
    with _SinAnimacion():
        cuerpo = Text()
        if plan.resumen:
            cuerpo.append(plan.resumen + "\n\n", style="bold")
        for indice, (paso, vista) in enumerate(zip(plan.pasos, vistas), start=1):
            cuerpo.append(f"{indice}. ", style=f"bold {AZUL_CLARO}")
            cuerpo.append(etiqueta(paso.herramienta) + "\n", style="bold")
            if vista is not None and vista.cambios:
                cuerpo.append_text(_lineas_vista(vista, "   "))
            else:
                cuerpo.append_text(_argumentos_legibles(paso.argumentos, "   "))
            cuerpo.append("\n")
        consola.print()
        consola.print(
            _panel_permiso(cuerpo, f"Esto es lo que haría ({len(plan.pasos)} pasos)")
        )
        return preguntar("¿Lo hago?")


def aprobar_receta(receta, preparados) -> bool:
    """Muestra qué hará una receta y pide una sola aprobación."""
    cuerpo = Text()
    if receta.descripcion:
        cuerpo.append(receta.descripcion + "\n\n", style="dim")
    for indice, paso in enumerate(preparados, start=1):
        cuerpo.append(f"{indice}. ", style=f"bold {AZUL_CLARO}")
        cuerpo.append(etiqueta(paso.herramienta) + "\n", style="bold")
        if paso.vista is not None and paso.vista.cambios:
            cuerpo.append_text(_lineas_vista(paso.vista, "   "))
        else:
            cuerpo.append_text(_argumentos_legibles(paso.argumentos, "   "))
        cuerpo.append("\n")
    consola.print(
        _panel_permiso(cuerpo, f"Receta «{receta.nombre}» ({len(preparados)} pasos)")
    )
    return preguntar("¿Lo hago?")


# --- resultados -------------------------------------------------------------


def _fecha_item(item: dict, carpeta: str) -> str:
    ruta = item.get("ruta") or (str(Path(carpeta) / item["nombre"]) if carpeta else "")
    if ruta:
        try:
            return fecha_legible(Path(ruta).stat().st_mtime)
        except OSError:
            pass
    if "dias" in item:
        return fecha_legible(time.time() - int(item["dias"]) * 86400)
    return ""


def tabla_archivos(datos: dict, titulo: str = "") -> RenderableType:
    """Tabla de archivos: nombre, tamaño legible y fecha (máximo 15 filas)."""
    items = datos.get("items", [])
    carpeta = datos.get("ruta", "")
    tabla = Table(
        title=titulo or None,
        title_justify="left",
        title_style=f"bold {AZUL_CLARO}",
        border_style=AZUL_CLARO,
        header_style="bold",
        show_edge=False,
        pad_edge=False,
    )
    tabla.add_column("Nombre", overflow="fold", ratio=1)
    tabla.add_column("Tamaño", justify="right", no_wrap=True)
    tabla.add_column("Fecha", justify="right", no_wrap=True, style="dim")

    for item in items[:MAX_FILAS]:
        es_carpeta = item.get("tipo") == "carpeta"
        icono = _s("carpeta") if es_carpeta else _s("archivo")
        tamano = "" if es_carpeta else item.get("tamano_legible", "")
        tabla.add_row(f"{icono} {item['nombre']}", tamano, _fecha_item(item, carpeta))

    total = max(int(datos.get("total") or 0), len(items))
    faltan = total - min(len(items), MAX_FILAS)
    if faltan > 0:
        nota = Text(f"…y {faltan} más" if not _simple() else f"...y {faltan} mas",
                    style="dim")
        return Group(tabla, nota)
    return tabla


# Compatibilidad con el nombre anterior.
def tabla_directorio(datos: dict) -> RenderableType:
    return tabla_archivos(datos, f"Contenido de {bonita(datos.get('ruta', ''))}")


_CON_TABLA = {"listar_directorio", "buscar_archivos"}


def mostrar_paso(paso) -> None:
    """Muestra el resultado de un paso ejecutado."""
    resultado = paso.resultado
    if not resultado.ok:
        consola.print(Text(f"{_s('fallo')} {resultado.resumen}", style=ROJO))
        return

    consola.print(
        Text(f"{_s('ok')} ", style=VERDE).append(
            _resumen_bonito(resultado.resumen), style="default"
        )
    )
    datos = resultado.datos or {}
    if paso.herramienta in _CON_TABLA and datos.get("items"):
        consola.print()
        consola.print(tabla_archivos(datos))
        consola.print()


def _resumen_bonito(texto: str) -> str:
    casa = str(Path.home())
    return texto.replace(casa, "~") if casa != "/" else texto


_CANCELADO = {"Cancelado por ti.", "No aprobaste el plan."}


def mostrar_ejecucion(ejecucion, modelo: str = "") -> None:
    """Muestra el resultado completo de una petición."""
    for paso in ejecucion.pasos:
        mostrar_paso(paso)

    if ejecucion.abortada:
        motivo = ejecucion.motivo_aborto or ""
        if motivo in _CANCELADO:
            cancelado("De acuerdo, no toqué nada.")
        elif "conectar con Ollama" in motivo:
            sin_ollama(modelo or "el modelo", "sin_conexion")
        else:
            problema(motivo)
        return

    if ejecucion.respuesta:
        consola.print()
        consola.print(
            con_mascota(
                "feliz",
                Panel(
                    _resumen_bonito(ejecucion.respuesta),
                    border_style=VERDE,
                    padding=(0, 2),
                ),
            )
        )


# --- avisos y errores -------------------------------------------------------


def cancelado(mensaje: str = "Cancelé esa petición.") -> None:
    consola.print()
    consola.print(con_mascota("normal", Text(mensaje, style=AMARILLO)))


def problema(mensaje: str, consejo: str = "") -> None:
    """Error explicado en español sencillo, con qué hacer."""
    consejo = consejo or "Prueba a decirlo de otra forma, o escribe «ayuda»."
    cuerpo = Text(_resumen_bonito(mensaje).strip() + "\n\n")
    cuerpo.append(consejo, style="dim")
    consola.print()
    consola.print(
        con_mascota(
            "preocupado",
            Panel(
                cuerpo,
                title="No pude hacerlo",
                title_align="left",
                border_style=ROJO,
                padding=(0, 2),
            ),
        )
    )


def error_inesperado(ruta_log: Path | None = None) -> None:
    """Fallo interno: nunca se enseña el traceback, solo dónde quedó anotado."""
    consejo = "Prueba otra vez o dilo de otra forma."
    if ruta_log is not None:
        consejo += f"\nLo anoté en {bonita(str(ruta_log))}"
    problema("Algo salió mal de mi lado y no pude terminar.", consejo)


def exito(mensaje: str) -> None:
    consola.print(Text(f"{_s('ok')} ", style=VERDE).append(mensaje, style="default"))


def error(mensaje: str) -> None:
    consola.print(Text(f"{_s('fallo')} {mensaje}", style=ROJO))


def aviso(mensaje: str) -> None:
    consola.print(Text(f"{_s('aviso')} {mensaje}", style=AMARILLO))


# --- recetas ----------------------------------------------------------------


def tabla_recetas(recetas) -> Table:
    """Lista las recetas guardadas."""
    tabla = Table(title="Recetas guardadas", border_style=AZUL_CLARO)
    tabla.add_column("Nombre", style=AZUL_CLARO, overflow="fold")
    tabla.add_column("Pasos", justify="right", style="dim")
    tabla.add_column("Usos", justify="right", style="dim")
    tabla.add_column("Descripción", overflow="fold")
    for receta in recetas:
        huecos = receta.huecos()
        descripcion = Text(receta.descripcion or "—")
        if huecos:
            descripcion.append(f" (pide: {', '.join(huecos)})", style=AMARILLO)
        tabla.add_row(
            receta.nombre, str(len(receta.pasos)), str(receta.veces_usada), descripcion
        )
    return tabla


def pedir_valor(nombre: str) -> str:
    """Pide al usuario el valor de un hueco de la receta."""
    return consola.input(f"[{AZUL_CLARO}]{nombre}[/]: ").strip()


# Reexportados para que la CLI no importe Rich directamente.
__all__ = [
    "consola",
    "Confirm",
    "Table",
    "Text",
    "EJEMPLOS",
    "Pensando",
    "bienvenida",
    "ayuda",
    "despedida",
    "sugerir_ejemplo",
    "sin_ollama",
    "anunciar_herramienta",
    "preguntar",
    "interpretar_respuesta",
    "pedir_confirmacion",
    "aprobar_plan",
    "aprobar_receta",
    "tabla_archivos",
    "tabla_directorio",
    "tabla_recetas",
    "pedir_valor",
    "mostrar_paso",
    "mostrar_ejecucion",
    "cancelado",
    "problema",
    "error_inesperado",
    "exito",
    "error",
    "aviso",
]
