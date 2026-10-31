"""Pruebas de los niveles de permiso."""

from asistente.safety.permisos import Decision, Nivel, evaluar


def test_libre_se_permite():
    assert evaluar(Nivel.LIBRE).decision is Decision.PERMITIR


def test_confirmacion_pregunta():
    assert evaluar(Nivel.CONFIRMACION).decision is Decision.PREGUNTAR


def test_bloqueado_deniega():
    veredicto = evaluar(Nivel.BLOQUEADO)
    assert veredicto.decision is Decision.DENEGAR
    assert not veredicto.permitida


def test_motivo_de_bloqueo_personalizado():
    veredicto = evaluar(Nivel.BLOQUEADO, motivo_bloqueo="sudo no permitido")
    assert "sudo" in veredicto.motivo
