"""Pruebas de comprimir, descomprimir y la protección contra zip slip."""

import tarfile
import zipfile

import pytest

from asistente.agent.vista_previa import calcular
from asistente.tools.comprimir import Comprimir, Descomprimir, entrada_segura


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla el diario y la papelera."""
    from asistente import config as config_mod

    monkeypatch.setattr(config_mod, "directorio_datos", lambda: tmp_path / "datos")
    return tmp_path


@pytest.fixture
def carpeta_con_datos(entorno):
    origen = entorno / "datos_origen"
    origen.mkdir()
    (origen / "uno.txt").write_text("hola " * 200, encoding="utf-8")
    (origen / "sub").mkdir()
    (origen / "sub" / "dos.txt").write_text("mundo " * 200, encoding="utf-8")
    return origen


# --- entrada_segura: el corazón de la protección ---


@pytest.mark.parametrize(
    "nombre",
    [
        "../fuera.txt",
        "../../.ssh/authorized_keys",
        "sub/../../fuera.txt",
        "/etc/passwd",
        "/absoluta.txt",
        "C:\\Windows\\system32\\x.dll",
        "",
        "..",
    ],
)
def test_entrada_insegura_se_rechaza(nombre, tmp_path):
    seguro, razon = entrada_segura(nombre, tmp_path)
    assert not seguro, f"{nombre!r} debió rechazarse"
    assert razon


@pytest.mark.parametrize(
    "nombre", ["normal.txt", "sub/anidado.txt", "a/b/c/profundo.txt", "con espacio.md"]
)
def test_entrada_normal_se_acepta(nombre, tmp_path):
    seguro, razon = entrada_segura(nombre, tmp_path)
    assert seguro, f"{nombre!r}: {razon}"


# --- Ataque real ---


def test_zip_slip_no_escribe_fuera(entorno):
    """Un ZIP preparado para escribir fuera del destino debe bloquearse."""
    victima = entorno / "VICTIMA.txt"
    victima.write_text("original", encoding="utf-8")

    malicioso = entorno / "malicioso.zip"
    with zipfile.ZipFile(malicioso, "w") as paquete:
        paquete.writestr("inocente.txt", "normal")
        paquete.writestr("../VICTIMA.txt", "sobrescrito")

    destino = entorno / "extraido"
    resultado = Descomprimir().run(
        Descomprimir.Params(origen=str(malicioso), destino=str(destino))
    )

    assert not resultado.ok
    assert "peligrosa" in resultado.resumen
    assert victima.read_text(encoding="utf-8") == "original", "no debió tocarse"
    assert not destino.exists(), "no debe crear nada si el archivo es peligroso"


def test_tar_con_enlace_que_escapa_se_rechaza(entorno):
    """Un enlace simbólico dentro del TAR es otra vía de escape."""
    malicioso = entorno / "malicioso.tar"
    with tarfile.open(malicioso, "w") as paquete:
        info = tarfile.TarInfo("escape")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../etc/passwd"
        paquete.addfile(info)

    resultado = Descomprimir().run(
        Descomprimir.Params(origen=str(malicioso), destino=str(entorno / "x"))
    )

    assert not resultado.ok
    assert "peligrosa" in resultado.resumen


def test_no_extrae_en_ruta_protegida(entorno):
    paquete = entorno / "normal.zip"
    with zipfile.ZipFile(paquete, "w") as zf:
        zf.writestr("a.txt", "x")

    resultado = Descomprimir().run(
        Descomprimir.Params(origen=str(paquete), destino="/etc/colado")
    )

    assert not resultado.ok
    assert "No extraigo" in resultado.resumen


# --- Ciclo normal ---


def test_comprimir_carpeta(carpeta_con_datos):
    resultado = Comprimir().run(Comprimir.Params(origen=str(carpeta_con_datos)))

    assert resultado.ok
    assert resultado.datos["archivos"] == 2
    assert resultado.datos["bytes_comprimido"] < resultado.datos["bytes_original"]
    assert zipfile.is_zipfile(resultado.datos["destino"])
    assert resultado.reversible


def test_comprimir_un_solo_archivo(entorno):
    archivo = entorno / "solo.txt"
    archivo.write_text("contenido", encoding="utf-8")

    resultado = Comprimir().run(Comprimir.Params(origen=str(archivo)))

    assert resultado.ok
    assert resultado.datos["archivos"] == 1


def test_comprimir_deja_el_original(carpeta_con_datos):
    Comprimir().run(Comprimir.Params(origen=str(carpeta_con_datos)))
    assert (carpeta_con_datos / "uno.txt").exists()


def test_comprimir_no_pisa_un_zip_existente(carpeta_con_datos, entorno):
    primero = Comprimir().run(Comprimir.Params(origen=str(carpeta_con_datos)))
    segundo = Comprimir().run(Comprimir.Params(origen=str(carpeta_con_datos)))

    assert primero.datos["destino"] != segundo.datos["destino"]


def test_comprimir_carpeta_vacia(entorno):
    vacia = entorno / "vacia"
    vacia.mkdir()

    resultado = Comprimir().run(Comprimir.Params(origen=str(vacia)))

    assert not resultado.ok
    assert "vacío" in resultado.resumen


def test_comprimir_origen_inexistente(entorno):
    resultado = Comprimir().run(
        Comprimir.Params(origen=str(entorno / "no_existe"))
    )
    assert not resultado.ok
    # El mensaje debe decir qué hacer, no solo qué pasó.
    assert "info_archivo" in resultado.resumen


def test_ciclo_completo_ida_y_vuelta(carpeta_con_datos, entorno):
    comprimido = Comprimir().run(Comprimir.Params(origen=str(carpeta_con_datos)))
    destino = entorno / "recuperado"

    resultado = Descomprimir().run(
        Descomprimir.Params(origen=comprimido.datos["destino"], destino=str(destino))
    )

    assert resultado.ok
    assert (destino / "uno.txt").read_text(encoding="utf-8").startswith("hola")
    assert (destino / "sub" / "dos.txt").exists()


def test_descomprimir_tar_gz(entorno):
    paquete = entorno / "p.tar.gz"
    contenido = entorno / "c.txt"
    contenido.write_text("desde tar", encoding="utf-8")
    with tarfile.open(paquete, "w:gz") as tf:
        tf.add(contenido, arcname="c.txt")

    destino = entorno / "salida"
    resultado = Descomprimir().run(
        Descomprimir.Params(origen=str(paquete), destino=str(destino))
    )

    assert resultado.ok
    assert (destino / "c.txt").read_text(encoding="utf-8") == "desde tar"


def test_descomprimir_archivo_corrupto(entorno):
    roto = entorno / "roto.zip"
    roto.write_bytes(b"no soy un zip")

    resultado = Descomprimir().run(Descomprimir.Params(origen=str(roto)))

    assert not resultado.ok
    assert "corrupto" in resultado.resumen


def test_descomprimir_inexistente(entorno):
    resultado = Descomprimir().run(
        Descomprimir.Params(origen=str(entorno / "nada.zip"))
    )
    assert not resultado.ok


def test_descomprimir_zip_vacio(entorno):
    vacio = entorno / "vacio.zip"
    with zipfile.ZipFile(vacio, "w"):
        pass

    resultado = Descomprimir().run(Descomprimir.Params(origen=str(vacio)))

    assert not resultado.ok
    assert "vacío" in resultado.resumen


# --- Vista previa ---


def test_vista_previa_de_comprimir(carpeta_con_datos):
    vista = calcular("comprimir", Comprimir.Params(origen=str(carpeta_con_datos)))

    assert vista is not None
    assert vista.reversible
    detalles = " ".join(c.detalle for c in vista.cambios)
    assert "2 archivos" in detalles
    assert "no se modifica" in detalles


def test_vista_previa_de_descomprimir(entorno):
    paquete = entorno / "v.zip"
    with zipfile.ZipFile(paquete, "w") as zf:
        zf.writestr("a.txt", "hola")
        zf.writestr("b.txt", "mundo")

    vista = calcular("descomprimir", Descomprimir.Params(origen=str(paquete)))

    assert vista is not None
    detalles = " ".join(c.detalle for c in vista.cambios)
    assert "2 elementos" in detalles


def test_vista_previa_avisa_si_el_destino_existe(entorno):
    paquete = entorno / "w.zip"
    with zipfile.ZipFile(paquete, "w") as zf:
        zf.writestr("a.txt", "x")
    ocupado = entorno / "ocupado"
    ocupado.mkdir()

    vista = calcular(
        "descomprimir",
        Descomprimir.Params(origen=str(paquete), destino=str(ocupado)),
    )

    assert vista.avisos
    assert "ya existe" in vista.avisos[0].lower()
