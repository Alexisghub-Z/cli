"""Pruebas de la interfaz: mascota, confirmaciones, pantallas y sesión.

Usan `Console(record=True)` para no depender de una terminal real.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from rich.console import Console

from asistente.cli import estilo, render, sesion
from asistente.cli.mascota import ALTO, ANCHO, ESTADOS, mascota
from asistente.tools.base import Resultado


class _TerminalASCII(io.StringIO):
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


@pytest.fixture
def consola(monkeypatch):
    nueva = _consola()
    monkeypatch.setattr(render, "consola", nueva)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv(estilo.VARIABLE_ASCII, raising=False)
    return nueva


def _texto(c: Console) -> str:
    return c.export_text()


# --- mascota ----------------------------------------------------------------


@pytest.mark.parametrize("estado", ESTADOS)
@pytest.mark.parametrize("ascii_", [False, True])
def test_mascota_todos_los_estados(estado, ascii_):
    c = _consola(simple=ascii_)
    c.print(mascota(estado, ascii=ascii_))
    lineas = _texto(c).rstrip("\n").split("\n")
    assert len(lineas) == ALTO
    assert all(len(linea.rstrip()) <= ANCHO for linea in lineas)


@pytest.mark.parametrize("estado", ESTADOS)
def test_mascota_ascii_solo_usa_ascii(estado):
    texto = mascota(estado, ascii=True).plain
    assert texto.isascii()
    assert not mascota(estado, ascii=True).spans  # sin colores


def test_mascota_unicode_lleva_colores_de_marca():
    texto = mascota("normal")
    estilos = " ".join(str(span.style) for span in texto.spans)
    assert estilo.AZUL_MARINO.lower() in estilos.lower()
    assert estilo.AZUL_CLARO.lower() in estilos.lower()


def test_expresiones_son_distintas():
    for ascii_ in (False, True):
        caras = {mascota(e, ascii=ascii_).plain for e in ESTADOS}
        assert len(caras) == len(ESTADOS)


def test_mismo_cuerpo_en_todas_las_expresiones():
    # La base y la coronilla no cambian: solo ojos, boca y el detalle.
    for ascii_ in (False, True):
        cuerpos = {
            tuple(mascota(e, ascii=ascii_).plain.split("\n")[i] for i in (1, 4))
            for e in ESTADOS
        }
        assert len(cuerpos) == 1


def test_parpadeo_cierra_los_ojos():
    abierta = mascota("normal").plain
    cerrada = mascota("normal", parpadeo=True).plain
    assert "●" in abierta and "●" not in cerrada


def test_puntos_de_pensando():
    for puntos in range(4):
        primera = mascota("pensando", puntos=puntos).plain.split("\n")[0]
        assert primera.count(".") == puntos


def test_estado_desconocido_no_rompe():
    assert mascota("inventado").plain == mascota("normal").plain


# --- compatibilidad ---------------------------------------------------------


def test_terminal_sin_unicode_usa_modo_simple(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv(estilo.VARIABLE_ASCII, raising=False)
    assert estilo.modo_simple(_consola(simple=True))
    assert not estilo.modo_simple(_consola())


def test_no_color_activa_modo_simple(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert estilo.modo_simple(_consola())


def test_variable_fuerza_ascii(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv(estilo.VARIABLE_ASCII, "1")
    assert estilo.modo_simple(_consola())


def test_terminal_angosta_oculta_la_mascota(monkeypatch):
    angosta = _consola(ancho=50)
    monkeypatch.setattr(render, "consola", angosta)
    render.despedida()
    texto = _texto(angosta)
    assert "Hasta luego" in texto
    assert "╰───────╯" not in texto


def test_pantallas_en_modo_ascii_no_usan_unicode_de_dibujo(monkeypatch):
    simple = _consola(simple=True)
    monkeypatch.setattr(render, "consola", simple)
    render.bienvenida("qwen3:8b", "conectado")
    texto = _texto(simple)
    assert "Soy Bruma" in texto
    assert not any(c in texto for c in "╭╮╰╯●›")


# --- confirmación -----------------------------------------------------------


@pytest.mark.parametrize("respuesta", ["s", "si", "sí", "Sí", "y", "yes", " S ", "si."])
def test_confirmacion_acepta(respuesta):
    assert render.interpretar_respuesta(respuesta)


@pytest.mark.parametrize(
    "respuesta", ["", "n", "no", "nop", "quizás", "sii", "ok", "claro", "1"]
)
def test_confirmacion_cancela(respuesta):
    assert not render.interpretar_respuesta(respuesta)


def test_si_con_tilde_descompuesta():
    assert render.interpretar_respuesta("sí")  # «sí» en forma NFD


def test_preguntar_por_defecto_es_no(consola, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert render.preguntar() is False
    assert "[s/N]" in _texto(consola)


def test_preguntar_acepta_si(consola, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "sí")
    assert render.preguntar() is True


def test_ctrl_c_en_la_pregunta_cancela(consola, monkeypatch):
    def interrumpir(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrumpir)
    assert render.preguntar() is False


def test_pedir_confirmacion_muestra_vista_y_respeta_respuesta(consola, monkeypatch):
    from asistente.agent.vista_previa import Cambio, VistaPrevia

    vista = VistaPrevia(
        "Papelera", [Cambio("eliminar", "foto.png a la papelera")], reversible=False
    )
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert render.pedir_confirmacion("enviar_a_papelera", "ruta=/x", vista) is False
    texto = _texto(consola)
    assert "Mandar a la papelera" in texto
    assert "foto.png a la papelera" in texto
    assert "no se puede deshacer" in texto
    assert "¿Lo hago?" in texto


def test_aprobar_plan(consola, monkeypatch):
    from asistente.agent.planner import PasoPlan, Plan

    plan = Plan("Ordenar", [PasoPlan("crear_carpeta", {"ruta": "~/X"})])
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    assert render.aprobar_plan(plan, [None]) is True
    assert "Crear una carpeta" in _texto(consola)


# --- pantallas --------------------------------------------------------------


def test_bienvenida_conectado(consola):
    render.bienvenida("qwen3:8b", "conectado")
    texto = _texto(consola)
    assert "¡Hola! Soy Bruma, te ayudo con tus archivos." in texto
    for numero, ejemplo in enumerate(render.EJEMPLOS, start=1):
        assert f"{numero}  {ejemplo}" in texto
    assert "● conectado" in texto


def test_bienvenida_sin_ollama_explica_que_hacer(consola):
    render.bienvenida("qwen3:8b", "sin_conexion")
    texto = _texto(consola)
    assert "ollama serve" in texto
    assert "ollama pull qwen3:8b" in texto
    assert "● sin conexión" in texto
    assert "Traceback" not in texto


def test_tabla_muestra_quince_y_cuantas_faltan(consola):
    items = [
        {"nombre": f"a{i}.txt", "tamano": i, "tamano_legible": f"{i} B", "dias": i}
        for i in range(20)
    ]
    consola.print(render.tabla_archivos({"ruta": "", "total": 20, "items": items}))
    texto = _texto(consola)
    assert "a14.txt" in texto and "a15.txt" not in texto
    assert "y 5 más" in texto


def test_resultado_feliz_y_error_preocupado(consola):
    paso = SimpleNamespace(
        herramienta="espacio_en_disco",
        argumentos={},
        resultado=Resultado(ok=True, resumen="100 GB libres de 500 GB"),
    )
    render.mostrar_ejecucion(
        SimpleNamespace(pasos=[paso], abortada=False, motivo_aborto="", respuesta="Hecho")
    )
    render.mostrar_ejecucion(
        SimpleNamespace(pasos=[], abortada=True, motivo_aborto="Ruta protegida", respuesta="")
    )
    texto = _texto(consola)
    assert "100 GB libres" in texto
    assert "^ ^" in texto  # feliz
    assert "ó ò" in texto  # preocupado
    assert "No pude hacerlo" in texto


def test_error_de_conexion_muestra_pasos_de_ollama(consola):
    render.mostrar_ejecucion(
        SimpleNamespace(
            pasos=[],
            abortada=True,
            motivo_aborto="No pude conectar con Ollama en http://x: refused",
            respuesta="",
        ),
        "qwen3:8b",
    )
    assert "ollama serve" in _texto(consola)


def test_fotograma_pensando(consola):
    consola.print(render.Pensando().fotograma(5.6))
    texto = _texto(consola)
    assert "Pensando" in texto and "5 s" in texto and "Ctrl+C" in texto


def test_frase_herramienta(consola):
    frase = render.frase_herramienta("buscar_archivos", {"ruta": "~/Descargas"})
    assert frase == "🔍 Buscando en Descargas..."


def test_frase_herramienta_ascii(monkeypatch):
    monkeypatch.setattr(render, "consola", _consola(simple=True))
    frase = render.frase_herramienta("buscar_archivos", {"ruta": "~/Descargas"})
    assert frase == "> Buscando en Descargas..."


def test_fecha_legible():
    ahora = 1_800_000_000.0
    assert render.fecha_legible(ahora, ahora) == "hoy"
    assert render.fecha_legible(ahora - 86400, ahora) == "ayer"
    assert render.fecha_legible(ahora - 3 * 86400, ahora) == "hace 3 días"
    assert render.fecha_legible(ahora - 40 * 86400, ahora).endswith("2026")


# --- sesión -----------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("salir", ("comando", "salir")),
        ("Ayuda", ("comando", "ayuda")),
        ("deshacer", ("comando", "deshacer")),
        ("limpiar", ("comando", "limpiar")),
        ("1", ("peticion", render.EJEMPLOS[0])),
        ("5", ("peticion", render.EJEMPLOS[4])),
        ("9", ("sugerir", "9")),
        ("", ("sugerir", "")),
        ("   ", ("sugerir", "")),
        ("asdfghjkl", ("sugerir", "asdfghjkl")),
        ("jajaja", ("sugerir", "jajaja")),
        ("???", ("sugerir", "???")),
        ("Busca los PDF de esta semana", ("peticion", "Busca los PDF de esta semana")),
        ("lista mi escritorio", ("peticion", "lista mi escritorio")),
    ],
)
def test_resolver_entrada(texto, esperado):
    assert sesion.resolver_entrada(texto, render.EJEMPLOS) == esperado


def test_ejemplos_no_parecen_sin_sentido():
    assert not any(sesion.parece_sin_sentido(e) for e in render.EJEMPLOS)


def test_estado_ollama():
    class Cliente:
        def __init__(self, ok, motivo="", falla=False):
            self.ok, self.motivo, self.falla = ok, motivo, falla

        def disponible(self):
            if self.falla:
                raise RuntimeError("boom")
            return self.ok, self.motivo

    assert sesion.estado_ollama(Cliente(True)) == "conectado"
    assert (
        sesion.estado_ollama(Cliente(False, "El modelo 'x' no está descargado."))
        == "sin_modelo"
    )
    assert sesion.estado_ollama(Cliente(False, "No encuentro Ollama")) == "sin_conexion"
    assert sesion.estado_ollama(Cliente(False, falla=True)) == "sin_conexion"


def test_registrar_error_guarda_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(sesion, "ruta_log", lambda: tmp_path / "errores.log")
    try:
        raise ValueError("fallo de prueba")
    except ValueError as exc:
        ruta = sesion.registrar_error(exc)
    contenido = ruta.read_text(encoding="utf-8")
    assert "Traceback" in contenido and "fallo de prueba" in contenido


def test_cliente_visible_anuncia_solo_herramientas_libres():
    from asistente.llm.base import LlamadaHerramienta, RespuestaModelo
    from asistente.tools import cargar_herramientas

    cargar_herramientas()
    anuncios = []

    class Falso:
        modelo = "x"

        def __init__(self):
            self.respuestas = [
                RespuestaModelo(texto="", llamadas=[LlamadaHerramienta("buscar_archivos", {})]),
                RespuestaModelo(texto="", llamadas=[LlamadaHerramienta("enviar_a_papelera", {})]),
                RespuestaModelo(texto="listo"),
            ]

        def responder(self, mensajes, herramientas=None):
            return self.respuestas.pop(0)

    cliente = sesion.ClienteVisible(Falso(), lambda n, a: anuncios.append(n))
    for _ in range(3):
        cliente.responder([])
    assert anuncios == ["buscar_archivos"]
    assert cliente.modelo == "x"  # delega lo demás
