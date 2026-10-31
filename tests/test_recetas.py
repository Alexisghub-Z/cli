"""Pruebas de las recetas: guardar, cargar, parametrizar y reproducir."""

import pytest

from asistente.agent.loop import Agente
from asistente.config import Config
from asistente.llm.simulado import ClienteSimulado
from asistente.recetas import ejecutor, modelo
from asistente.tools.base import Resultado


class _PasoFalso:
    """Imita un Paso de una ejecución real."""

    def __init__(self, herramienta, argumentos, ok=True, resumen="hecho"):
        self.herramienta = herramienta
        self.argumentos = argumentos
        self.resultado = Resultado(ok=ok, resumen=resumen)


@pytest.fixture
def carpeta(tmp_path):
    destino = tmp_path / "recetas"
    destino.mkdir()
    return destino


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    from asistente import config as config_mod

    monkeypatch.setattr(config_mod, "directorio_datos", lambda: tmp_path / "datos")
    return tmp_path


def _autorizador():
    """El comprobador de permisos real del agente."""
    return Agente(ClienteSimulado(), Config())._autorizar


# --- Construir recetas ---


def test_desde_pasos_omite_consultas():
    """Una receta repite acciones, no consultas."""
    pasos = [
        _PasoFalso("listar_directorio", {"ruta": "~/x"}),
        _PasoFalso("espacio_en_disco", {}),
        _PasoFalso("crear_carpeta", {"ruta": "~/x/Nueva"}),
    ]
    receta, problema = modelo.desde_pasos("mi tarea", pasos)

    assert receta is not None, problema
    assert len(receta.pasos) == 1
    assert receta.pasos[0].herramienta == "crear_carpeta"


def test_solo_consultas_no_es_receta():
    pasos = [_PasoFalso("procesos", {}), _PasoFalso("espacio_en_disco", {})]
    receta, problema = modelo.desde_pasos("nada", pasos)

    assert receta is None
    assert "solo consultó" in problema


def test_omite_los_pasos_que_fallaron():
    pasos = [
        _PasoFalso("crear_carpeta", {"ruta": "/a"}, ok=False),
        _PasoFalso("crear_carpeta", {"ruta": "/b"}, ok=True),
    ]
    receta, _ = modelo.desde_pasos("mixta", pasos)

    assert len(receta.pasos) == 1
    assert receta.pasos[0].argumentos["ruta"] == "/b"


def test_no_guarda_comandos_de_shell():
    """Un comando arbitrario no es reproducible con garantías."""
    pasos = [_PasoFalso("ejecutar_comando", {"comando": "git status"})]
    receta, problema = modelo.desde_pasos("comando", pasos)

    assert receta is None
    assert "ejecutar_comando" in problema


# --- Huecos ---


def test_detecta_huecos():
    receta = modelo.Receta(
        nombre="x",
        pasos=[
            modelo.PasoReceta("crear_carpeta", {"ruta": "{carpeta}/PDF"}),
            modelo.PasoReceta(
                "mover", {"origen": "{carpeta}/a.pdf", "destino": "{otro}"}
            ),
        ],
    )
    assert receta.huecos() == ["carpeta", "otro"]


def test_resuelve_huecos():
    paso = modelo.PasoReceta("mover", {"origen": "{c}/a.txt", "destino": "{c}/sub"})
    resueltos = paso.resolver({"c": "/home/x"})

    assert resueltos == {"origen": "/home/x/a.txt", "destino": "/home/x/sub"}


def test_hueco_sin_valor_se_detecta(entorno):
    receta = modelo.Receta(
        nombre="x",
        pasos=[modelo.PasoReceta("crear_carpeta", {"ruta": "{falta}/sub"})],
    )
    preparados, problema = ejecutor.preparar(receta, {}, _autorizador())

    assert preparados == []
    assert "falta" in problema


def test_argumentos_no_texto_se_conservan():
    paso = modelo.PasoReceta("listar", {"ruta": "{c}", "incluir_ocultos": True})
    assert paso.resolver({"c": "/x"})["incluir_ocultos"] is True


# --- Guardar y cargar ---


def test_ida_y_vuelta(carpeta):
    original = modelo.Receta(
        nombre="Organizar PDF",
        descripcion="mueve los PDF",
        pasos=[modelo.PasoReceta("crear_carpeta", {"ruta": "{c}/PDF"})],
    )
    modelo.guardar(original, carpeta)
    recuperada = modelo.buscar("Organizar PDF", carpeta)

    assert recuperada is not None
    assert recuperada.nombre == "Organizar PDF"
    assert recuperada.descripcion == "mueve los PDF"
    assert recuperada.pasos[0].argumentos == {"ruta": "{c}/PDF"}


def test_busca_sin_distinguir_mayusculas(carpeta):
    modelo.guardar(modelo.Receta(nombre="Mi Receta", pasos=[
        modelo.PasoReceta("crear_carpeta", {"ruta": "/x"})]), carpeta)

    assert modelo.buscar("mi receta", carpeta) is not None
    assert modelo.buscar("MI RECETA", carpeta) is not None


def test_receta_inexistente(carpeta):
    assert modelo.buscar("no existe", carpeta) is None


def test_json_corrupto_no_rompe(carpeta):
    (carpeta / "mala.json").write_text("{ esto no es json", encoding="utf-8")
    (carpeta / "buena.json").write_text(
        '{"nombre": "Buena", "pasos": [{"herramienta": "crear_carpeta", '
        '"argumentos": {"ruta": "/x"}}]}',
        encoding="utf-8",
    )
    recetas = modelo.todas(carpeta)

    assert len(recetas) == 1
    assert recetas[0].nombre == "Buena"


def test_receta_sin_pasos_se_descarta(carpeta):
    (carpeta / "vacia.json").write_text(
        '{"nombre": "Vacia", "pasos": []}', encoding="utf-8"
    )
    assert modelo.todas(carpeta) == []


def test_carpeta_inexistente_devuelve_vacio(tmp_path):
    assert modelo.todas(tmp_path / "no_existe") == []


@pytest.mark.parametrize(
    "nombre,valido",
    [
        ("Organizar PDF", True),
        ("limpiar_descargas", True),
        ("Año nuevo", True),
        ("", False),
        ("   ", False),
        ("con/barra", False),
        ("../escape", False),
        ("x" * 61, False),
    ],
)
def test_validacion_del_nombre(nombre, valido):
    assert modelo.nombre_valido(nombre)[0] is valido


def test_nombre_de_archivo_seguro():
    assert modelo.archivo_de("Organizar PDF") == "organizar-pdf.json"
    assert "/" not in modelo.archivo_de("Año  Nuevo")


# --- Reproducir ---


def test_reproduce_una_receta(entorno):
    destino = entorno / "trabajo"
    destino.mkdir()
    receta = modelo.Receta(
        nombre="Crear estructura",
        pasos=[
            modelo.PasoReceta("crear_carpeta", {"ruta": "{base}/Uno"}),
            modelo.PasoReceta("crear_carpeta", {"ruta": "{base}/Dos"}),
        ],
    )
    preparados, problema = ejecutor.preparar(
        receta, {"base": str(destino)}, _autorizador()
    )
    assert not problema
    resultado = ejecutor.ejecutar(preparados)

    assert resultado.ok
    assert (destino / "Uno").is_dir()
    assert (destino / "Dos").is_dir()


def test_la_receta_no_se_salta_las_rutas_protegidas(entorno):
    """Una receta no es un atajo al sistema de permisos."""
    receta = modelo.Receta(
        nombre="mala",
        pasos=[modelo.PasoReceta("crear_carpeta", {"ruta": "/etc/colado"})],
    )
    preparados, problema = ejecutor.preparar(receta, {}, _autorizador())

    assert preparados == []
    assert "bloqueado" in problema


def test_herramienta_que_ya_no_existe(entorno):
    receta = modelo.Receta(
        nombre="vieja",
        pasos=[modelo.PasoReceta("herramienta_borrada", {})],
    )
    preparados, problema = ejecutor.preparar(receta, {}, _autorizador())

    assert preparados == []
    assert "ya no existe" in problema


def test_parametros_invalidos_se_detectan(entorno):
    receta = modelo.Receta(
        nombre="mal",
        pasos=[modelo.PasoReceta("crear_carpeta", {"parametro_raro": "x"})],
    )
    preparados, problema = ejecutor.preparar(receta, {}, _autorizador())

    assert preparados == []
    assert "paso 1" in problema.lower()


def test_se_detiene_si_un_paso_falla(entorno):
    destino = entorno / "t"
    destino.mkdir()
    (destino / "YaExiste").mkdir()
    receta = modelo.Receta(
        nombre="parcial",
        pasos=[
            modelo.PasoReceta("crear_carpeta", {"ruta": str(destino / "Uno")}),
            modelo.PasoReceta("crear_carpeta", {"ruta": str(destino / "YaExiste")}),
            modelo.PasoReceta("crear_carpeta", {"ruta": str(destino / "Tres")}),
        ],
    )
    preparados, _ = ejecutor.preparar(receta, {}, _autorizador())
    resultado = ejecutor.ejecutar(preparados)

    assert resultado.abortada
    assert len(resultado.pasos) == 2
    assert not (destino / "Tres").exists(), "no debe seguir tras un fallo"


def test_la_vista_previa_acompana_cada_paso(entorno):
    receta = modelo.Receta(
        nombre="con vista",
        pasos=[modelo.PasoReceta("crear_carpeta", {"ruta": str(entorno / "V")})],
    )
    preparados, _ = ejecutor.preparar(receta, {}, _autorizador())

    assert preparados[0].vista is not None
    assert preparados[0].vista.cambios


def test_contador_de_usos(carpeta):
    receta = modelo.Receta(
        nombre="contada",
        pasos=[modelo.PasoReceta("crear_carpeta", {"ruta": "/x"})],
        veces_usada=3,
    )
    modelo.guardar(receta, carpeta)
    assert modelo.buscar("contada", carpeta).veces_usada == 3
