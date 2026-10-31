"""Pruebas de leer_archivo, buscar_archivos y las de sistema."""

from pathlib import Path

from asistente.tools.buscar import BuscarArchivos
from asistente.tools.leer import LeerArchivo
from asistente.tools.sistema import EspacioEnDisco, Procesos


def test_lee_texto(tmp_path):
    archivo = tmp_path / "notas.txt"
    archivo.write_text("una\ndos\ntres\n", encoding="utf-8")

    resultado = LeerArchivo().run(LeerArchivo.Params(ruta=str(archivo)))

    assert resultado.ok
    assert resultado.datos["lineas"] == 3
    assert "dos" in resultado.datos["contenido"]


def test_recorta_por_max_lineas(tmp_path):
    archivo = tmp_path / "largo.txt"
    archivo.write_text("\n".join(str(i) for i in range(100)), encoding="utf-8")

    resultado = LeerArchivo().run(
        LeerArchivo.Params(ruta=str(archivo), max_lineas=10)
    )

    assert resultado.datos["recortado"]
    assert len(resultado.datos["contenido"].splitlines()) == 10


def test_detecta_binario(tmp_path):
    archivo = tmp_path / "raro.bin"
    archivo.write_bytes(b"\x00\x01\x02binario")

    resultado = LeerArchivo().run(LeerArchivo.Params(ruta=str(archivo)))

    assert not resultado.ok
    assert "binario" in resultado.resumen


def test_no_lee_configuracion_sensible():
    """El modelo no debe poder ver claves privadas."""
    resultado = LeerArchivo().run(
        LeerArchivo.Params(ruta=str(Path.home() / ".ssh" / "id_rsa"))
    )
    assert not resultado.ok


def test_carpeta_en_lugar_de_archivo(tmp_path):
    resultado = LeerArchivo().run(LeerArchivo.Params(ruta=str(tmp_path)))
    assert not resultado.ok
    assert "listar_directorio" in resultado.resumen


def test_busca_por_extension(tmp_path):
    (tmp_path / "a.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.pdf").write_text("z", encoding="utf-8")

    resultado = BuscarArchivos().run(
        BuscarArchivos.Params(ruta=str(tmp_path), extension="pdf")
    )

    assert resultado.datos["total"] == 2, "debe entrar en subcarpetas"


def test_busca_por_nombre(tmp_path):
    (tmp_path / "informe-2026.txt").write_text("x", encoding="utf-8")
    (tmp_path / "otro.txt").write_text("y", encoding="utf-8")

    resultado = BuscarArchivos().run(
        BuscarArchivos.Params(ruta=str(tmp_path), nombre="informe")
    )

    assert resultado.datos["total"] == 1


def test_busca_por_tamano(tmp_path):
    (tmp_path / "grande.bin").write_bytes(b"x" * 200_000)
    (tmp_path / "pequeno.txt").write_text("x", encoding="utf-8")

    resultado = BuscarArchivos().run(
        BuscarArchivos.Params(ruta=str(tmp_path), tamano_minimo_mb=0.1)
    )

    assert resultado.datos["total"] == 1
    assert resultado.datos["items"][0]["nombre"] == "grande.bin"


def test_busqueda_sin_resultados(tmp_path):
    resultado = BuscarArchivos().run(
        BuscarArchivos.Params(ruta=str(tmp_path), extension="xyz")
    )
    assert resultado.ok
    assert resultado.datos["total"] == 0
    assert "No encontré" in resultado.resumen


def test_busqueda_ignora_carpetas_de_ruido(tmp_path):
    ruido = tmp_path / "node_modules"
    ruido.mkdir()
    (ruido / "lib.js").write_text("x", encoding="utf-8")
    (tmp_path / "mio.js").write_text("y", encoding="utf-8")

    resultado = BuscarArchivos().run(
        BuscarArchivos.Params(ruta=str(tmp_path), extension="js")
    )

    assert resultado.datos["total"] == 1
    assert resultado.datos["items"][0]["nombre"] == "mio.js"


def test_espacio_en_disco(tmp_path):
    resultado = EspacioEnDisco().run(EspacioEnDisco.Params(ruta=str(tmp_path)))
    assert resultado.ok
    assert resultado.datos["total"] > 0
    assert 0 <= resultado.datos["porcentaje_usado"] <= 100


def test_procesos():
    resultado = Procesos().run(Procesos.Params(limite=5))
    assert resultado.ok
    assert 0 < resultado.datos["total"] <= 5
    assert resultado.datos["items"][0]["nombre"]


def test_procesos_es_de_solo_lectura():
    from asistente.safety.permisos import Nivel

    assert Procesos.nivel is Nivel.LIBRE
