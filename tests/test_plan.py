"""Pruebas del plan de varios pasos y de la vista previa."""

import json

import pytest

from asistente.agent.loop import Agente
from asistente.agent.planner import proponer
from asistente.agent.vista_previa import calcular
from asistente.llm.simulado import ClienteSimulado
from asistente.tools.archivos import CrearCarpeta, EnviarAPapelera, Mover
from asistente.tools.comando import EjecutarComando
from asistente.tools.listar import ListarDirectorio


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla diario y papelera."""
    from asistente import config as config_mod

    monkeypatch.setattr(config_mod, "directorio_datos", lambda: tmp_path / "datos")
    return tmp_path


def _plan_json(pasos, resumen="Plan de prueba"):
    return json.dumps(
        {"multipaso": True, "resumen": resumen, "pasos": pasos}, ensure_ascii=False
    )


# --- Vista previa ---


def test_vista_previa_de_mover(tmp_path):
    origen = tmp_path / "a.txt"
    origen.write_text("x", encoding="utf-8")

    vista = calcular(
        "mover", Mover.Params(origen=str(origen), destino=str(tmp_path / "b.txt"))
    )

    assert vista is not None
    assert vista.reversible
    tipos = {c.tipo for c in vista.cambios}
    assert "mover" in tipos and "eliminar" in tipos


def test_vista_previa_avisa_de_colision(tmp_path):
    origen = tmp_path / "c.txt"
    origen.write_text("nuevo", encoding="utf-8")
    choque = tmp_path / "ya.txt"
    choque.write_text("viejo", encoding="utf-8")

    vista = calcular(
        "mover", Mover.Params(origen=str(origen), destino=str(choque))
    )

    assert vista.avisos, "debe avisar de que el destino existe"
    assert "otro nombre" in vista.avisos[0]


def test_vista_previa_lista_carpetas_intermedias(tmp_path):
    destino = tmp_path / "uno" / "dos" / "tres"

    vista = calcular("crear_carpeta", CrearCarpeta.Params(ruta=str(destino)))

    detalles = " ".join(c.detalle for c in vista.cambios)
    assert "intermedias" in detalles


def test_vista_previa_de_papelera_dice_que_es_reversible(tmp_path):
    archivo = tmp_path / "d.txt"
    archivo.write_text("x", encoding="utf-8")

    vista = calcular("enviar_a_papelera", EnviarAPapelera.Params(ruta=str(archivo)))

    assert vista.reversible
    assert any("deshacer" in aviso for aviso in vista.avisos)


def test_vista_previa_de_comando_no_es_reversible():
    vista = calcular(
        "ejecutar_comando", EjecutarComando.Params(comando="git status")
    )
    assert vista is not None
    assert not vista.reversible


def test_sin_vista_previa_si_no_modifica():
    """Las herramientas de solo lectura no necesitan vista previa."""
    assert calcular("listar_directorio", ListarDirectorio.Params(ruta=".")) is None


# --- Planner ---


def test_propone_plan_de_varios_pasos(entorno):
    texto = _plan_json(
        [
            {
                "herramienta": "crear_carpeta",
                "argumentos": {"ruta": str(entorno / "PDF")},
                "motivo": "carpeta destino",
            },
            {
                "herramienta": "crear_carpeta",
                "argumentos": {"ruta": str(entorno / "JPG")},
                "motivo": "otra carpeta",
            },
        ],
        resumen="Organizar por tipo",
    )
    plan = proponer(ClienteSimulado([ClienteSimulado.con_texto(texto)]), "organiza")

    assert plan is not None
    assert plan.multipaso
    assert plan.resumen == "Organizar por tipo"
    assert len(plan.pasos) == 2


def test_tarea_de_un_paso_no_genera_plan():
    cliente = ClienteSimulado([ClienteSimulado.con_texto('{"multipaso": false}')])
    assert proponer(cliente, "lista mis descargas") is None


def test_plan_con_herramienta_inventada_se_descarta():
    texto = _plan_json(
        [
            {"herramienta": "no_existe", "argumentos": {}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": "/tmp/x"}},
        ]
    )
    cliente = ClienteSimulado([ClienteSimulado.con_texto(texto)])
    assert proponer(cliente, "haz algo") is None


def test_plan_en_bloque_markdown():
    """El modelo suele envolver el JSON en ```json."""
    interno = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": "/tmp/a"}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": "/tmp/b"}},
        ]
    )
    cliente = ClienteSimulado(
        [ClienteSimulado.con_texto(f"Aquí tienes:\n```json\n{interno}\n```")]
    )
    assert proponer(cliente, "crea dos carpetas") is not None


def test_respuesta_sin_json_no_rompe():
    cliente = ClienteSimulado([ClienteSimulado.con_texto("No entendí la petición.")])
    assert proponer(cliente, "???") is None


def test_plan_respeta_el_maximo_de_pasos():
    pasos = [
        {"herramienta": "crear_carpeta", "argumentos": {"ruta": f"/tmp/c{i}"}}
        for i in range(10)
    ]
    cliente = ClienteSimulado([ClienteSimulado.con_texto(_plan_json(pasos))])
    plan = proponer(cliente, "crea muchas", max_pasos=3)

    assert plan is not None
    assert len(plan.pasos) == 3


# --- Plan dentro del agente ---


def test_plan_aprobado_se_ejecuta_sin_preguntar_por_paso(entorno):
    """Una sola aprobación cubre todos los pasos."""
    texto = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "A")}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "B")}},
        ]
    )
    preguntas: list[str] = []

    agente = Agente(
        ClienteSimulado([ClienteSimulado.con_texto(texto)]),
        confirmador=lambda n, d, v: preguntas.append(n) or True,
        aprobador_plan=lambda plan, vistas: True,
    )
    resultado = agente.ejecutar("crea las carpetas A y B")

    assert not resultado.abortada
    assert len(resultado.pasos) == 2
    assert (entorno / "A").is_dir() and (entorno / "B").is_dir()
    assert preguntas == [], "el plan aprobado no debe preguntar de nuevo"


def test_plan_rechazado_no_ejecuta_nada(entorno):
    texto = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "X")}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "Y")}},
        ]
    )
    agente = Agente(
        ClienteSimulado([ClienteSimulado.con_texto(texto)]),
        aprobador_plan=lambda plan, vistas: False,
    )
    resultado = agente.ejecutar("crea X e Y")

    assert resultado.abortada
    assert "No aprobaste" in resultado.motivo_aborto
    assert not (entorno / "X").exists()
    assert not (entorno / "Y").exists()


def test_el_aprobador_recibe_las_vistas_previas(entorno):
    texto = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "P")}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "Q")}},
        ]
    )
    recibidas: list = []

    def aprobar(plan, vistas):
        recibidas.extend(vistas)
        return False

    Agente(
        ClienteSimulado([ClienteSimulado.con_texto(texto)]),
        aprobador_plan=aprobar,
    ).ejecutar("crea P y Q")

    assert len(recibidas) == 2
    assert all(v is not None for v in recibidas), "debe haber vista previa"


def test_plan_con_ruta_protegida_se_deniega_antes_de_mostrarlo(entorno):
    """Un plan que toca /etc no se le ofrece al usuario como viable."""
    texto = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": "/etc/nuevo"}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "Z")}},
        ]
    )
    aprobaciones: list = []

    resultado = Agente(
        ClienteSimulado([ClienteSimulado.con_texto(texto)]),
        aprobador_plan=lambda p, v: aprobaciones.append(p) or True,
    ).ejecutar("crea carpetas")

    assert resultado.abortada
    assert aprobaciones == [], "no debe pedirse aprobación de un plan bloqueado"
    assert not (entorno / "Z").exists()


def test_plan_se_detiene_si_un_paso_falla(entorno):
    """El segundo paso falla; el tercero no debe ejecutarse."""
    existente = entorno / "YaExiste"
    existente.mkdir()
    texto = _plan_json(
        [
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "Uno")}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(existente)}},
            {"herramienta": "crear_carpeta", "argumentos": {"ruta": str(entorno / "Tres")}},
        ]
    )
    resultado = Agente(
        ClienteSimulado([ClienteSimulado.con_texto(texto)]),
        aprobador_plan=lambda p, v: True,
    ).ejecutar("crea tres carpetas")

    assert resultado.abortada
    assert len(resultado.pasos) == 2
    assert (entorno / "Uno").is_dir()
    assert not (entorno / "Tres").exists(), "no debe seguir tras un fallo"


def test_sin_aprobador_cae_a_paso_a_paso(entorno):
    """Sin forma de aprobar un plan, se usa el modo paso a paso."""
    agente = Agente(
        ClienteSimulado(
            [
                ClienteSimulado.con_herramienta(
                    "listar_directorio", ruta=str(entorno)
                ),
                ClienteSimulado.con_texto("Carpeta vacía."),
            ]
        ),
    )
    resultado = agente.ejecutar("qué hay aquí")

    assert not resultado.abortada
    assert resultado.plan is None
    assert len(resultado.pasos) == 1
