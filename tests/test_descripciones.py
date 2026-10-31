"""Pruebas de las descripciones de herramientas.

El modelo elige la herramienta leyendo su `descripcion`, así que una
descripción ambigua es un fallo de verdad, no un detalle de estilo. La
evaluación (`evals/`) lo mide con el modelo real; estas pruebas protegen
las propiedades que podemos comprobar sin modelo.
"""

from __future__ import annotations

import pytest

from asistente.safety.permisos import Nivel
from asistente.tools import cargar_herramientas, registro

cargar_herramientas()
TODAS = registro.todas()


def test_hay_herramientas_registradas():
    assert len(TODAS) >= 14


@pytest.mark.parametrize("nombre", sorted(TODAS))
def test_toda_descripcion_dice_cuando_usarla(nombre):
    """Una descripción debe orientar la elección, no solo nombrar la acción."""
    descripcion = TODAS[nombre].descripcion.lower()
    assert len(descripcion) > 40, f"{nombre}: descripción demasiado corta"
    pistas = ("úsala", "usa esto", "es la herramienta", "úsalo")
    assert any(p in descripcion for p in pistas), (
        f"{nombre}: la descripción no dice cuándo usarla"
    )


@pytest.mark.parametrize("nombre", sorted(TODAS))
def test_descripcion_en_espanol(nombre):
    """Todo lo que ve el usuario y el modelo va en español."""
    descripcion = TODAS[nombre].descripcion
    assert any(c in descripcion for c in "áéíóúñÁÉÍÓÚÑ¿¡"), (
        f"{nombre}: la descripción no parece estar en español"
    )


@pytest.mark.parametrize("nombre", sorted(TODAS))
def test_esquemas_planos(nombre):
    """Los modelos de 3B-8B se pierden con parámetros anidados."""
    propiedades = (
        TODAS[nombre].esquema_json()["function"]["parameters"].get("properties", {})
    )
    for campo, definicion in propiedades.items():
        assert definicion.get("type") != "object", (
            f"{nombre}.{campo} es un objeto anidado"
        )


@pytest.mark.parametrize("nombre", sorted(TODAS))
def test_todo_parametro_esta_descrito(nombre):
    """El modelo rellena los parámetros leyendo su description."""
    propiedades = (
        TODAS[nombre].esquema_json()["function"]["parameters"].get("properties", {})
    )
    for campo, definicion in propiedades.items():
        assert definicion.get("description"), f"{nombre}.{campo} sin description"


# --- Confusiones concretas que la evaluación detectó con el modelo real ---


def test_eliminar_apunta_a_la_papelera():
    """«elimina esa carpeta» eligió mover en la evaluación (qwen2.5:3b).

    Es el fallo más grave posible: mover sí modifica archivos, así que el
    usuario podría aprobar un desplazamiento creyendo que desecha algo.
    """
    papelera = TODAS["enviar_a_papelera"].descripcion.lower()
    for verbo in ("elimina", "borra"):
        assert verbo in papelera, f"la papelera no menciona «{verbo}»"

    # Y mover debe decir explícitamente que no sirve para eso.
    mover = TODAS["mover"].descripcion.lower()
    assert "enviar_a_papelera" in mover, (
        "mover debería redirigir a enviar_a_papelera para eliminar"
    )


def test_leer_e_info_no_se_confunden():
    """«ábreme el README y dime de qué trata» eligió info_archivo."""
    leer = TODAS["leer_archivo"].descripcion.lower()
    info = TODAS["info_archivo"].descripcion.lower()

    assert "de qué trata" in leer or "qué dice" in leer
    # info_archivo debe negar explícitamente que muestre el contenido.
    assert "no abre" in info or "no muestra" in info
    assert "leer_archivo" in info, "info_archivo debería redirigir a leer_archivo"


def test_buscar_y_listar_no_se_confunden():
    """«¿dónde está el archivo informe?» eligió listar_directorio."""
    buscar = TODAS["buscar_archivos"].descripcion.lower()
    listar = TODAS["listar_directorio"].descripcion.lower()

    assert "dónde está" in buscar or "encontrar" in buscar
    assert "buscar_archivos" in listar, (
        "listar_directorio debería redirigir a buscar_archivos"
    )


def test_las_destructivas_requieren_confirmacion():
    """Nada que modifique archivos puede ser de nivel libre."""
    modifican = {
        "mover", "copiar", "renombrar", "crear_carpeta",
        "enviar_a_papelera", "comprimir", "descomprimir", "ejecutar_comando",
    }
    for nombre in modifican & set(TODAS):
        assert TODAS[nombre].nivel is Nivel.CONFIRMACION, (
            f"{nombre} modifica archivos y debe pedir confirmación"
        )


def test_las_de_consulta_son_libres():
    for nombre in {
        "listar_directorio", "buscar_archivos", "leer_archivo",
        "info_archivo", "espacio_en_disco", "procesos",
    } & set(TODAS):
        assert TODAS[nombre].nivel is Nivel.LIBRE, f"{nombre} solo consulta"
