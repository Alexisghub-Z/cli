"""Pruebas de info_archivo y de los mensajes de error accionables."""

import pytest

from asistente.safety.permisos import Nivel
from asistente.tools.archivos import Mover
from asistente.tools.info import InfoArchivo, describir_tipo
from asistente.tools.leer import LeerArchivo
from asistente.tools.listar import ListarDirectorio


def _info(ruta):
    return InfoArchivo().run(InfoArchivo.Params(ruta=str(ruta)))


def test_datos_de_un_archivo(tmp_path):
    archivo = tmp_path / "notas.txt"
    archivo.write_text("hola mundo", encoding="utf-8")

    resultado = _info(archivo)

    assert resultado.ok
    assert resultado.datos["nombre"] == "notas.txt"
    assert resultado.datos["tipo"] == "texto"
    assert resultado.datos["tamano"] == 10
    assert resultado.datos["permisos"].startswith("-")
    assert "hace" in resultado.datos["modificado_hace"]


def test_datos_de_una_carpeta(tmp_path):
    (tmp_path / "a.txt").write_text("x" * 100, encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("y" * 50, encoding="utf-8")

    resultado = _info(tmp_path)

    assert resultado.ok
    assert resultado.datos["tipo"] == "carpeta"
    # El tamaño útil de una carpeta es el de su contenido.
    assert resultado.datos["contenido"]["archivos"] == 2
    assert resultado.datos["contenido"]["carpetas"] == 1
    assert resultado.datos["tamano"] == 150


def test_carpeta_vacia(tmp_path):
    resultado = _info(tmp_path)
    assert resultado.ok
    assert resultado.datos["contenido"]["archivos"] == 0


def test_ruta_inexistente_sugiere_que_hacer(tmp_path):
    resultado = _info(tmp_path / "no_existe.txt")
    assert not resultado.ok
    assert "buscar_archivos" in resultado.resumen


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("foto.JPG", "imagen JPEG"),
        ("doc.pdf", "documento PDF"),
        ("script.py", "código Python"),
        ("datos.csv", "tabla CSV"),
        ("paquete.zip", "archivo comprimido ZIP"),
        ("sin_extension", "archivo sin extensión"),
        ("raro.xyz", "archivo xyz"),
    ],
)
def test_describe_el_tipo(tmp_path, nombre, esperado):
    archivo = tmp_path / nombre
    archivo.write_text("x", encoding="utf-8")
    assert describir_tipo(archivo) == esperado


def test_es_de_solo_lectura():
    assert InfoArchivo.nivel is Nivel.LIBRE


def test_esquema_plano():
    """Los modelos pequeños se pierden con parámetros anidados."""
    propiedades = InfoArchivo.esquema_json()["function"]["parameters"]["properties"]
    assert all(d.get("type") != "object" for d in propiedades.values())


# --- Mensajes accionables (tarea B4) ---


def test_listar_un_archivo_sugiere_leer_archivo(tmp_path):
    archivo = tmp_path / "x.txt"
    archivo.write_text("x", encoding="utf-8")

    resultado = ListarDirectorio().run(ListarDirectorio.Params(ruta=str(archivo)))

    assert not resultado.ok
    assert "leer_archivo" in resultado.resumen


def test_listar_ruta_inexistente_sugiere_buscar(tmp_path):
    resultado = ListarDirectorio().run(
        ListarDirectorio.Params(ruta=str(tmp_path / "nada"))
    )
    assert "buscar_archivos" in resultado.resumen


def test_leer_inexistente_sugiere_buscar(tmp_path):
    resultado = LeerArchivo().run(LeerArchivo.Params(ruta=str(tmp_path / "no.txt")))
    assert "buscar_archivos" in resultado.resumen


def test_mover_inexistente_sugiere_buscar(tmp_path):
    resultado = Mover().run(
        Mover.Params(origen=str(tmp_path / "no"), destino=str(tmp_path / "si"))
    )
    assert "buscar_archivos" in resultado.resumen


def test_todos_los_errores_son_accionables(tmp_path):
    """Un error debe decir qué hacer, no solo qué pasó."""
    casos = [
        ListarDirectorio().run(ListarDirectorio.Params(ruta=str(tmp_path / "a"))),
        LeerArchivo().run(LeerArchivo.Params(ruta=str(tmp_path / "b"))),
        InfoArchivo().run(InfoArchivo.Params(ruta=str(tmp_path / "c"))),
    ]
    pistas = ("usa", "prueba", "comprueba", "elige", "indica")
    for resultado in casos:
        assert not resultado.ok
        assert any(p in resultado.resumen.lower() for p in pistas), resultado.resumen
