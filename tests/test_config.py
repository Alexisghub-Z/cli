"""Pruebas de la configuración TOML."""

from asistente.config import Config, cargar, directorio_config, guardar


def test_valores_por_defecto():
    cfg = Config()
    assert cfg.modelo == "qwen3:8b"
    assert cfg.max_pasos == 8
    assert cfg.confirmar_siempre is True


def test_ida_y_vuelta(tmp_path):
    ruta = tmp_path / "config.toml"
    guardar(Config(modelo="qwen2.5:3b", max_pasos=4, temperatura=0.5), ruta)

    cfg = cargar(ruta)
    assert cfg.modelo == "qwen2.5:3b"
    assert cfg.max_pasos == 4
    assert cfg.temperatura == 0.5


def test_archivo_inexistente_usa_defectos(tmp_path):
    assert cargar(tmp_path / "no_existe.toml").modelo == Config().modelo


def test_toml_corrupto_no_rompe(tmp_path):
    ruta = tmp_path / "roto.toml"
    ruta.write_text("esto no es [ toml válido", encoding="utf-8")
    assert cargar(ruta).modelo == Config().modelo


def test_claves_desconocidas_se_ignoran(tmp_path):
    ruta = tmp_path / "extra.toml"
    ruta.write_text('modelo = "x:1b"\nclave_rara = 9\n', encoding="utf-8")
    cfg = cargar(ruta)
    assert cfg.modelo == "x:1b"


def test_directorio_config_es_absoluto():
    assert directorio_config().is_absolute()
