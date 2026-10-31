"""Pruebas de la herramienta listar_directorio."""

from asistente.tools.listar import ListarDirectorio, formato_tamano


def _listar(**kwargs):
    herramienta = ListarDirectorio()
    return herramienta.run(ListarDirectorio.Params(**kwargs))


def test_lista_archivos_y_carpetas(tmp_path):
    (tmp_path / "uno.txt").write_text("hola", encoding="utf-8")
    (tmp_path / "dos.md").write_text("mundo", encoding="utf-8")
    (tmp_path / "carpeta").mkdir()

    resultado = _listar(ruta=str(tmp_path))

    assert resultado.ok
    assert resultado.datos["total"] == 3
    nombres = [i["nombre"] for i in resultado.datos["items"]]
    assert nombres[0] == "carpeta", "las carpetas van primero"
    assert set(nombres) == {"carpeta", "uno.txt", "dos.md"}


def test_oculta_los_puntos_por_defecto(tmp_path):
    (tmp_path / "visible.txt").touch()
    (tmp_path / ".oculto").touch()

    assert _listar(ruta=str(tmp_path)).datos["total"] == 1
    assert _listar(ruta=str(tmp_path), incluir_ocultos=True).datos["total"] == 2


def test_ruta_inexistente_da_error():
    resultado = _listar(ruta="/ruta/que/no/existe/jamas")
    assert not resultado.ok
    assert "No existe" in resultado.resumen


def test_archivo_en_lugar_de_carpeta(tmp_path):
    archivo = tmp_path / "soy_archivo.txt"
    archivo.write_text("x", encoding="utf-8")

    resultado = _listar(ruta=str(archivo))
    assert not resultado.ok
    assert "No es una carpeta" in resultado.resumen


def test_carpeta_vacia(tmp_path):
    resultado = _listar(ruta=str(tmp_path))
    assert resultado.ok
    assert resultado.datos["total"] == 0


def test_tamano_legible():
    assert formato_tamano(0) == "0 B"
    assert formato_tamano(512) == "512 B"
    assert formato_tamano(2048) == "2.0 KB"
    assert formato_tamano(5 * 1024 * 1024) == "5.0 MB"


def test_esquema_para_el_modelo():
    esquema = ListarDirectorio.esquema_json()
    assert esquema["function"]["name"] == "listar_directorio"
    propiedades = esquema["function"]["parameters"]["properties"]
    assert "ruta" in propiedades
    # Los esquemas deben ser planos: nada de objetos anidados (modelos 3B-8B).
    for definicion in propiedades.values():
        assert definicion.get("type") != "object"
