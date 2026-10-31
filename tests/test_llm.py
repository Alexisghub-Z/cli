"""Pruebas del cliente del modelo (sin modelo real)."""

from asistente.llm.ollama import _parsear_argumentos, extraer_llamada_del_texto
from asistente.llm.simulado import ClienteSimulado


def test_argumentos_como_diccionario():
    assert _parsear_argumentos({"ruta": "."}) == {"ruta": "."}


def test_argumentos_como_cadena_json():
    """Los modelos pequeños a veces mandan los argumentos como texto."""
    assert _parsear_argumentos('{"ruta": "~/x"}') == {"ruta": "~/x"}


def test_argumentos_basura_no_rompen():
    assert _parsear_argumentos("no soy json") == {}
    assert _parsear_argumentos(None) == {}


def test_rescata_llamada_en_bloque_markdown():
    texto = '```json\n{"name": "listar_directorio", "arguments": {"ruta": "."}}\n```'
    llamada = extraer_llamada_del_texto(texto)
    assert llamada is not None
    assert llamada.nombre == "listar_directorio"
    assert llamada.argumentos == {"ruta": "."}


def test_rescata_llamada_en_json_plano():
    llamada = extraer_llamada_del_texto('{"nombre": "procesos", "argumentos": {}}')
    assert llamada is not None
    assert llamada.nombre == "procesos"


def test_texto_normal_no_es_llamada():
    assert extraer_llamada_del_texto("Hola, tienes 3 archivos.") is None


def test_cliente_simulado_devuelve_en_orden():
    cliente = ClienteSimulado(
        [ClienteSimulado.con_texto("uno"), ClienteSimulado.con_texto("dos")]
    )
    assert cliente.responder([]).texto == "uno"
    assert cliente.responder([]).texto == "dos"
    assert cliente.responder([]).texto == "Listo."
