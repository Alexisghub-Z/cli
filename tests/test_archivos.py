"""Pruebas de las herramientas que modifican archivos, y del deshacer."""

import pytest

from asistente.tools.archivos import (
    Copiar,
    CrearCarpeta,
    EnviarAPapelera,
    Mover,
    Renombrar,
)
from asistente.undo.diario import Diario
from asistente.undo.revertir import revertir


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla el diario y la papelera en una carpeta temporal."""
    from asistente import config as config_mod

    datos = tmp_path / "datos"
    monkeypatch.setattr(config_mod, "directorio_datos", lambda: datos)
    return tmp_path


def _diario_de(entorno):
    return Diario(entorno / "datos" / "diario.jsonl")


def test_mover_archivo(entorno):
    origen = entorno / "a.txt"
    origen.write_text("hola", encoding="utf-8")
    destino = entorno / "sub" / "a.txt"

    resultado = Mover().run(Mover.Params(origen=str(origen), destino=str(destino)))

    assert resultado.ok
    assert destino.read_text(encoding="utf-8") == "hola"
    assert not origen.exists()
    assert resultado.reversible


def test_mover_a_carpeta_existente(entorno):
    origen = entorno / "b.txt"
    origen.write_text("x", encoding="utf-8")
    carpeta = entorno / "destino"
    carpeta.mkdir()

    Mover().run(Mover.Params(origen=str(origen), destino=str(carpeta)))

    assert (carpeta / "b.txt").exists()


def test_mover_no_pisa_el_destino(entorno):
    origen = entorno / "c.txt"
    origen.write_text("nuevo", encoding="utf-8")
    existente = entorno / "sub" / "c.txt"
    existente.parent.mkdir()
    existente.write_text("viejo", encoding="utf-8")

    Mover().run(Mover.Params(origen=str(origen), destino=str(existente)))

    assert existente.read_text(encoding="utf-8") == "viejo", "no debe pisarse"
    assert (entorno / "sub" / "c-1.txt").read_text(encoding="utf-8") == "nuevo"


def test_mover_origen_inexistente(entorno):
    resultado = Mover().run(
        Mover.Params(origen=str(entorno / "nada.txt"), destino=str(entorno / "x.txt"))
    )
    assert not resultado.ok
    assert "No existe" in resultado.resumen


def test_copiar_deja_el_original(entorno):
    origen = entorno / "d.txt"
    origen.write_text("contenido", encoding="utf-8")
    destino = entorno / "copia.txt"

    resultado = Copiar().run(
        Copiar.Params(origen=str(origen), destino=str(destino))
    )

    assert resultado.ok
    assert origen.exists()
    assert destino.read_text(encoding="utf-8") == "contenido"


def test_renombrar(entorno):
    origen = entorno / "viejo.txt"
    origen.write_text("x", encoding="utf-8")

    resultado = Renombrar().run(
        Renombrar.Params(ruta=str(origen), nombre_nuevo="nuevo.txt")
    )

    assert resultado.ok
    assert (entorno / "nuevo.txt").exists()
    assert not origen.exists()


@pytest.mark.parametrize("malo", ["../fuera.txt", "sub/dentro.txt", "..", "."])
def test_renombrar_rechaza_rutas(entorno, malo):
    """Un nombre con separadores sería un movimiento disfrazado."""
    origen = entorno / "e.txt"
    origen.write_text("x", encoding="utf-8")

    resultado = Renombrar().run(
        Renombrar.Params(ruta=str(origen), nombre_nuevo=malo)
    )

    assert not resultado.ok
    assert origen.exists()


def test_crear_carpeta(entorno):
    destino = entorno / "uno" / "dos"
    resultado = CrearCarpeta().run(CrearCarpeta.Params(ruta=str(destino)))

    assert resultado.ok
    assert destino.is_dir()


def test_crear_carpeta_existente(entorno):
    destino = entorno / "ya"
    destino.mkdir()
    assert not CrearCarpeta().run(CrearCarpeta.Params(ruta=str(destino))).ok


def test_papelera_mueve_y_no_borra(entorno):
    archivo = entorno / "basura.txt"
    archivo.write_text("adios", encoding="utf-8")

    resultado = EnviarAPapelera().run(EnviarAPapelera.Params(ruta=str(archivo)))

    assert resultado.ok
    assert not archivo.exists()
    # El contenido sigue existiendo en la papelera: nada se borra de verdad.
    guardado = entorno / "datos" / "papelera"
    copias = list(guardado.iterdir())
    assert len(copias) == 1
    assert copias[0].read_text(encoding="utf-8") == "adios"


# --- Deshacer ---


def test_deshacer_mover(entorno):
    origen = entorno / "f.txt"
    origen.write_text("datos", encoding="utf-8")
    destino = entorno / "otro" / "f.txt"
    Mover().run(Mover.Params(origen=str(origen), destino=str(destino)))

    diario = _diario_de(entorno)
    ok, mensaje = revertir(diario.ultima(), diario)

    assert ok, mensaje
    assert origen.read_text(encoding="utf-8") == "datos"
    assert not destino.exists()


def test_deshacer_papelera_recupera(entorno):
    archivo = entorno / "recuperable.txt"
    archivo.write_text("importante", encoding="utf-8")
    EnviarAPapelera().run(EnviarAPapelera.Params(ruta=str(archivo)))
    assert not archivo.exists()

    diario = _diario_de(entorno)
    ok, _ = revertir(diario.ultima(), diario)

    assert ok
    assert archivo.read_text(encoding="utf-8") == "importante"


def test_deshacer_copiar_elimina_la_copia(entorno):
    origen = entorno / "g.txt"
    origen.write_text("x", encoding="utf-8")
    copia = entorno / "g-copia.txt"
    Copiar().run(Copiar.Params(origen=str(origen), destino=str(copia)))

    diario = _diario_de(entorno)
    ok, _ = revertir(diario.ultima(), diario)

    assert ok
    assert origen.exists(), "el original no se toca"
    assert not copia.exists()


def test_deshacer_carpeta_con_contenido_se_niega(entorno):
    """No borramos una carpeta donde el usuario ya metió cosas."""
    carpeta = entorno / "nueva"
    CrearCarpeta().run(CrearCarpeta.Params(ruta=str(carpeta)))
    (carpeta / "del_usuario.txt").write_text("mío", encoding="utf-8")

    diario = _diario_de(entorno)
    ok, mensaje = revertir(diario.ultima(), diario)

    assert not ok
    assert carpeta.exists()
    assert "archivos dentro" in mensaje


def test_deshacer_marca_y_no_repite(entorno):
    origen = entorno / "h.txt"
    origen.write_text("x", encoding="utf-8")
    Mover().run(
        Mover.Params(origen=str(origen), destino=str(entorno / "movido.txt"))
    )

    diario = _diario_de(entorno)
    assert len(diario.pendientes()) == 1
    revertir(diario.ultima(), diario)
    assert diario.pendientes() == [], "ya no debe quedar pendiente"
