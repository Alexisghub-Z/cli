"""Pruebas del bucle del agente, con modelo simulado (sin modelo real)."""

import pytest
from pydantic import BaseModel, Field

from asistente.agent.loop import Agente
from asistente.config import Config
from asistente.llm.base import ErrorModelo, RespuestaModelo
from asistente.llm.simulado import ClienteSimulado
from asistente.safety.permisos import Nivel
from asistente.tools import registro
from asistente.tools.base import Herramienta, Resultado


@pytest.fixture
def herramienta_falsa():
    """Registra una herramienta de prueba y la quita al terminar."""
    ejecuciones: list[dict] = []

    class Escribir(Herramienta):
        nombre = "escribir_prueba"
        descripcion = "Herramienta de prueba que requiere confirmación."
        nivel = Nivel.CONFIRMACION

        class Params(BaseModel):
            ruta: str = Field(description="Ruta destino.")

        def run(self, params):
            ejecuciones.append({"ruta": params.ruta})
            return Resultado(ok=True, resumen=f"Escrito en {params.ruta}")

    registro.registrar(Escribir)
    yield ejecuciones
    registro._REGISTRO.pop("escribir_prueba", None)


def test_responde_sin_herramientas():
    cliente = ClienteSimulado([ClienteSimulado.con_texto("Hola, ¿qué tal?")])
    resultado = Agente(cliente).ejecutar("saluda")

    assert resultado.respuesta == "Hola, ¿qué tal?"
    assert resultado.pasos == []


def test_usa_una_herramienta_y_resume(tmp_path):
    (tmp_path / "a.txt").touch()
    cliente = ClienteSimulado(
        [
            ClienteSimulado.con_herramienta("listar_directorio", ruta=str(tmp_path)),
            ClienteSimulado.con_texto("Hay 1 archivo."),
        ]
    )
    resultado = Agente(cliente).ejecutar("qué hay en esa carpeta")

    assert len(resultado.pasos) == 1
    assert resultado.pasos[0].herramienta == "listar_directorio"
    assert resultado.respuesta == "Hay 1 archivo."


def test_el_prompt_del_sistema_va_en_espanol():
    cliente = ClienteSimulado([ClienteSimulado.con_texto("ok")])
    Agente(cliente).ejecutar("hola")

    sistema = cliente.recibidos[0][0]
    assert sistema["role"] == "system"
    assert "español" in sistema["content"]


def test_sin_confirmador_no_ejecuta_accion_que_requiere_permiso(herramienta_falsa):
    """Por defecto se deniega: nunca asumimos un sí que el usuario no dio."""
    cliente = ClienteSimulado(
        [ClienteSimulado.con_herramienta("escribir_prueba", ruta="/tmp/x")]
    )
    resultado = Agente(cliente).ejecutar("escribe algo")

    assert resultado.abortada
    assert herramienta_falsa == [], "no debió ejecutarse"


def test_usuario_rechaza_la_confirmacion(herramienta_falsa):
    cliente = ClienteSimulado(
        [ClienteSimulado.con_herramienta("escribir_prueba", ruta="/tmp/x")]
    )
    agente = Agente(cliente, confirmador=lambda n, d, v: False)
    resultado = agente.ejecutar("escribe algo")

    assert resultado.abortada
    assert "Cancelado" in resultado.motivo_aborto
    assert herramienta_falsa == []


def test_usuario_acepta_la_confirmacion(herramienta_falsa, tmp_path):
    destino = str(tmp_path / "nuevo.txt")
    cliente = ClienteSimulado(
        [
            ClienteSimulado.con_herramienta("escribir_prueba", ruta=destino),
            ClienteSimulado.con_texto("Hecho."),
        ]
    )
    agente = Agente(cliente, confirmador=lambda n, d, v: True)
    resultado = agente.ejecutar("escribe algo")

    assert not resultado.abortada
    assert herramienta_falsa == [{"ruta": destino}]


def test_ruta_protegida_se_deniega_aunque_el_usuario_confirme(herramienta_falsa):
    """La ruta protegida gana sobre la confirmación del usuario."""
    cliente = ClienteSimulado(
        [ClienteSimulado.con_herramienta("escribir_prueba", ruta="/etc/passwd")]
    )
    agente = Agente(cliente, confirmador=lambda n, d, v: True)
    resultado = agente.ejecutar("modifica passwd")

    assert resultado.abortada
    assert "/etc/passwd" in resultado.motivo_aborto
    assert herramienta_falsa == [], "jamás debe tocar una ruta protegida"


def test_herramienta_inexistente_se_corrige_y_continua(tmp_path):
    cliente = ClienteSimulado(
        [
            ClienteSimulado.con_herramienta("herramienta_inventada", x=1),
            ClienteSimulado.con_herramienta("listar_directorio", ruta=str(tmp_path)),
            ClienteSimulado.con_texto("Carpeta vacía."),
        ]
    )
    resultado = Agente(cliente).ejecutar("lista")

    assert not resultado.abortada
    assert resultado.respuesta == "Carpeta vacía."


def test_parametros_invalidos_se_reintentan(tmp_path):
    """Pydantic rechaza, el error vuelve al modelo y este corrige."""
    cliente = ClienteSimulado(
        [
            ClienteSimulado.con_herramienta("listar_directorio", ruta=12345),
            ClienteSimulado.con_herramienta("listar_directorio", ruta=str(tmp_path)),
            ClienteSimulado.con_texto("Listo."),
        ]
    )
    resultado = Agente(cliente).ejecutar("lista")

    assert not resultado.abortada
    assert len(resultado.pasos) == 1


def test_detecta_ciclo_de_llamada_repetida(tmp_path):
    repetida = ClienteSimulado.con_herramienta(
        "listar_directorio", ruta=str(tmp_path)
    )
    cliente = ClienteSimulado(
        [
            repetida,
            ClienteSimulado.con_herramienta("listar_directorio", ruta=str(tmp_path)),
        ]
    )
    resultado = Agente(cliente).ejecutar("lista en bucle")

    assert resultado.abortada
    assert "ciclo" in resultado.motivo_aborto


def test_limite_de_pasos(tmp_path):
    """Nunca debe girar para siempre."""
    # Cada llamada usa una ruta distinta, para aislar el límite de pasos
    # del detector de llamadas repetidas.
    muchas = []
    for i in range(20):
        sub = tmp_path / f"sub{i}"
        sub.mkdir()
        muchas.append(
            ClienteSimulado.con_herramienta("listar_directorio", ruta=str(sub))
        )
    cliente = ClienteSimulado(muchas)
    agente = Agente(cliente, config=Config(max_pasos=3))
    resultado = agente.ejecutar("lista sin parar")

    assert resultado.abortada
    assert "límite" in resultado.motivo_aborto
    assert len(resultado.pasos) <= 3


def test_error_del_modelo_se_reporta_en_espanol():
    class Roto(ClienteSimulado):
        def responder(self, mensajes, herramientas=None):
            raise ErrorModelo("No pude conectar con Ollama")

    resultado = Agente(Roto()).ejecutar("hola")

    assert resultado.abortada
    assert "Ollama" in resultado.motivo_aborto
