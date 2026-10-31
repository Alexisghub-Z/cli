"""Pruebas del sistema de rutas protegidas."""

import sys
from pathlib import Path

import pytest

from asistente.safety.rutas import dentro_de, es_protegida


@pytest.mark.skipif(sys.platform == "win32", reason="rutas POSIX")
@pytest.mark.parametrize(
    "ruta",
    ["/etc", "/etc/passwd", "/usr/bin/python3", "/boot", "/sys/kernel"],
)
def test_rutas_del_sistema_estan_protegidas(ruta):
    protegida, motivo = es_protegida(ruta)
    assert protegida
    assert motivo


@pytest.mark.parametrize(
    "relativo", [".ssh", ".ssh/id_rsa", ".gnupg", ".aws/credentials"]
)
def test_config_sensible_del_home_protegida(relativo):
    protegida, _ = es_protegida(Path.home() / relativo)
    assert protegida


def test_home_completo_protegido():
    assert es_protegida(Path.home())[0]


def test_raiz_protegida():
    assert es_protegida(Path(Path.cwd().anchor))[0]


def test_carpeta_de_trabajo_no_protegida(tmp_path):
    archivo = tmp_path / "notas.txt"
    archivo.write_text("hola", encoding="utf-8")
    assert not es_protegida(archivo)[0]
    assert not es_protegida(tmp_path)[0]


def test_escape_con_puntos_detectado(tmp_path):
    """`..` no debe permitir salir de la base autorizada."""
    assert dentro_de(tmp_path / "sub", tmp_path)
    assert not dentro_de(tmp_path / ".." / "..", tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")
def test_symlink_a_ruta_protegida_se_detecta(tmp_path):
    """Un enlace inocente que apunta a /etc debe quedar bloqueado."""
    enlace = tmp_path / "parece_inofensivo"
    try:
        enlace.symlink_to("/etc")
    except OSError:
        pytest.skip("sin permiso para crear symlinks")
    assert es_protegida(enlace)[0]
