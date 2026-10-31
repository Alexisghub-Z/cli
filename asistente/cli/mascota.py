"""Bruma, la mascota del asistente: un fantasmita azul marino con antenita.

Diseño propio: cabeza redondeada con una antenita de punta brillante, base
lisa y redonda como una gota (nada de zigzag) y una colita de bruma «~» que
se le escapa por un lado. Mide 5 líneas de alto y 12 columnas de ancho.

Todas las expresiones comparten el cuerpo; solo cambian ojos, boca y un
detalle encima de la cabeza («...» al pensar, «?» al preguntar).
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from asistente.cli.estilo import AZUL_CLARO, AZUL_MARINO

ESTADOS = ("normal", "pensando", "feliz", "preocupado", "preguntando")

ANCHO = 12
ALTO = 5

# estado: (ojo izquierdo, ojo derecho, boca, mirando a un lado)
_CARAS_UNICODE = {
    "normal": ("●", "●", "◡", False),
    "pensando": ("●", "●", "·", True),
    "feliz": ("^", "^", "▽", False),
    "preocupado": ("ó", "ò", "~", False),
    "preguntando": ("●", "◕", "o", False),
}
_CARAS_ASCII = {
    "normal": ("o", "o", "u", False),
    "pensando": ("o", "o", ".", True),
    "feliz": ("^", "^", "w", False),
    "preocupado": ("o", "o", "~", False),
    "preguntando": ("o", "O", "o", False),
}

_CONTORNO_UNICODE = set("╭╮╰╯─│┴")

_ESTILO_CONTORNO = Style(color=AZUL_CLARO, bold=True)
_ESTILO_RELLENO = Style(bgcolor=AZUL_MARINO)
_ESTILO_CARA = Style(color="white", bgcolor=AZUL_MARINO, bold=True)
_ESTILO_DETALLE = Style(color=AZUL_CLARO, bold=True)
_ESTILO_COLA = Style(color=AZUL_CLARO, dim=True)


def _extra(estado: str, puntos: int, simple: bool) -> str:
    """Lo que flota junto a la antenita: «...» o «?»."""
    if estado == "pensando":
        return ("." * max(0, min(puntos, 3))).ljust(3)
    if estado == "preguntando":
        return "?  "
    return "   "


def _lineas(estado: str, simple: bool, parpadeo: bool, puntos: int) -> list[str]:
    caras = _CARAS_ASCII if simple else _CARAS_UNICODE
    izq, der, boca, a_un_lado = caras[estado]
    if parpadeo:
        izq = der = "-" if simple else "─"

    # Interior de la línea de los ojos: 5 columnas.
    ojos = f"  {izq} {der}" if a_un_lado else f" {izq} {der} "
    extra = _extra(estado, puntos, simple)

    if simple:
        return [
            f"      o {extra} ",
            "   .--+--.  ",
            f"  .'{ojos}'. ",
            f"  |   {boca}   | ",
            "  '-------'~",
        ]
    return [
        f"      • {extra} ",
        "   ╭──┴──╮  ",
        f"  ╭╯{ojos}╰╮ ",
        f"  │   {boca}   │ ",
        "  ╰───────╯~",
    ]


def _colorear(linea: str, indice: int) -> Text:
    """Contorno azul claro, cuerpo relleno de azul marino y cara blanca."""
    texto = Text(linea)
    if indice == 0:  # antenita y detalle flotante
        texto.stylize(_ESTILO_DETALLE)
        return texto

    posiciones = [i for i, c in enumerate(linea) if c in _CONTORNO_UNICODE]
    for i in posiciones:
        texto.stylize(_ESTILO_CONTORNO, i, i + 1)
    if indice == 1:  # la coronilla no tiene relleno
        return texto

    if len(posiciones) >= 2:
        # El interior es lo que queda entre el contorno izquierdo y el
        # derecho (en la línea de los ojos, el contorno ocupa dos columnas).
        izquierda = 3 if indice == 2 else posiciones[0]
        derecha = posiciones[-2] if indice == 2 else posiciones[-1]
        if indice == ALTO - 1:  # la base es contorno puro
            texto.stylize(_ESTILO_COLA, len(linea) - 1, len(linea))
            return texto
        for i in range(izquierda + 1, derecha):
            estilo = _ESTILO_RELLENO if linea[i] == " " else _ESTILO_CARA
            texto.stylize(estilo, i, i + 1)
    return texto


def mascota(
    estado: str = "normal",
    *,
    ascii: bool = False,
    parpadeo: bool = False,
    puntos: int = 3,
) -> Text:
    """Devuelve a Bruma lista para `console.print`.

    - `estado`: normal, pensando, feliz, preocupado o preguntando.
    - `ascii`: versión solo ASCII y sin color, para terminales limitadas.
    - `parpadeo`: ojos cerrados (un fotograma de la animación).
    - `puntos`: cuántos puntos del «...» se ven al pensar (0 a 3).
    """
    if estado not in ESTADOS:
        estado = "normal"
    lineas = _lineas(estado, ascii, parpadeo, puntos)
    if ascii:
        return Text("\n".join(lineas), no_wrap=True)

    resultado = Text(no_wrap=True)
    for indice, linea in enumerate(lineas):
        if indice:
            resultado.append("\n")
        resultado.append_text(_colorear(linea, indice))
    return resultado
