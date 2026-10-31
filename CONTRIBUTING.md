# Guía para contribuir

¡Gracias por querer ayudar! Este documento explica cómo trabajar en el
proyecto y, sobre todo, **cómo agregar una herramienta nueva**.

## Preparar el entorno

```bash
git clone https://github.com/Alexisghub-Z/cli.git
cd cli
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                           # debe pasar todo, sin Ollama instalado
```

No necesitas Ollama para desarrollar ni para correr las pruebas: solo para
probar el asistente con un modelo real.

## Principios que no se negocian

1. **El modelo nunca ejecuta nada.** Solo propone llamadas a herramientas.
2. **La seguridad se decide en el agente, no en la herramienta.** Nunca metas
   comprobaciones de permiso dentro de `run()`: declara el `nivel` y deja que
   el bucle decida. Así un olvido en una herramienta no abre un agujero.
3. **Todo en español**: mensajes, descripciones, errores y comentarios.
4. **Nada de rutas fijas.** Usa `pathlib`; tiene que funcionar en Linux, macOS
   y Windows.
5. **Esquemas planos.** El asistente está pensado para modelos de 3B–8B, que se
   pierden con parámetros anidados. Nada de objetos dentro de objetos.

## Agregar una herramienta nueva

Son cuatro pasos. Como ejemplo, una herramienta que cuenta líneas de un archivo.

### 1. Crea el archivo `asistente/tools/contar.py`

```python
"""Herramienta: contar las líneas de un archivo de texto."""

from __future__ import annotations

from pydantic import BaseModel, Field

from asistente.safety.permisos import Nivel
from asistente.safety.rutas import resolver
from asistente.tools.base import Herramienta, Resultado
from asistente.tools.registro import registrar


@registrar
class ContarLineas(Herramienta):
    # El nombre que verá el modelo: en español, con guiones bajos.
    nombre = "contar_lineas"

    # La descripción es un prompt: el modelo decide con ella. Sé concreto
    # y di cuándo usarla.
    descripcion = (
        "Cuenta las líneas de un archivo de texto. "
        "Úsala cuando el usuario pregunte el tamaño de un archivo en líneas."
    )

    # Solo lee: nivel LIBRE. Si modificara algo, sería CONFIRMACION.
    nivel = Nivel.LIBRE

    class Params(BaseModel):
        # Describe cada campo: el modelo lee estas descripciones.
        ruta: str = Field(description="Ruta del archivo, por ejemplo '~/notas.txt'.")

    def run(self, params: Params) -> Resultado:
        destino = resolver(params.ruta)

        # Valida y devuelve errores claros, en español.
        if not destino.is_file():
            return Resultado.error(f"No es un archivo: {destino}")

        try:
            total = sum(1 for _ in destino.open(encoding="utf-8", errors="replace"))
        except OSError as exc:
            return Resultado.error(f"No pude leer {destino}: {exc}")

        return Resultado(
            ok=True,
            resumen=f"{destino.name} tiene {total} líneas",
            datos={"ruta": str(destino), "lineas": total},
        )
```

### 2. Regístrala en `asistente/tools/__init__.py`

```python
def cargar_herramientas() -> None:
    from asistente.tools import listar      # noqa: F401
    from asistente.tools import contar      # noqa: F401   ← añade esta línea
```

### 3. Escribe las pruebas en `tests/test_contar.py`

Cubre siempre: el caso que funciona, el archivo que no existe, y los casos
límite (archivo vacío, sin permisos, ruta que es una carpeta).

```python
from asistente.tools.contar import ContarLineas


def _contar(**kwargs):
    return ContarLineas().run(ContarLineas.Params(**kwargs))


def test_cuenta_lineas(tmp_path):
    archivo = tmp_path / "notas.txt"
    archivo.write_text("una\ndos\ntres\n", encoding="utf-8")

    resultado = _contar(ruta=str(archivo))

    assert resultado.ok
    assert resultado.datos["lineas"] == 3


def test_archivo_vacio(tmp_path):
    archivo = tmp_path / "vacio.txt"
    archivo.touch()
    assert _contar(ruta=str(archivo)).datos["lineas"] == 0


def test_ruta_inexistente():
    resultado = _contar(ruta="/no/existe.txt")
    assert not resultado.ok
    assert "No es un archivo" in resultado.resumen
```

Usa siempre el fixture `tmp_path` de pytest: **nunca** escribas en carpetas
reales del usuario durante las pruebas.

### 4. Comprueba que todo pasa

```bash
pytest
asistente herramientas     # tu herramienta debe aparecer en la tabla
```

## Si tu herramienta modifica archivos

- Declara `nivel = Nivel.CONFIRMACION`.
- Asegúrate de que `rutas_afectadas()` devuelve **todas** las rutas que vas a
  tocar. El agente las comprueba contra la lista de rutas protegidas; si te
  dejas una fuera, te saltas la protección. Los campos `ruta`, `origen`,
  `destino` y `carpeta` se detectan solos; si usas otro nombre, sobrescribe
  el método.
- **Nunca borres de forma permanente.** Mueve a la papelera del asistente.
- Registra la operación en `undo/` para que se pueda deshacer.

## Pruebas con el modelo

Nunca hagas que una prueba dependa de un modelo real: sería lenta y daría
resultados distintos cada vez. Usa `ClienteSimulado`:

```python
from asistente.agent.loop import Agente
from asistente.llm.simulado import ClienteSimulado


def test_el_agente_usa_mi_herramienta(tmp_path):
    cliente = ClienteSimulado([
        ClienteSimulado.con_herramienta("contar_lineas", ruta=str(tmp_path / "a.txt")),
        ClienteSimulado.con_texto("El archivo tiene 3 líneas."),
    ])
    resultado = Agente(cliente).ejecutar("cuántas líneas tiene a.txt")
    assert resultado.pasos[0].herramienta == "contar_lineas"
```

## Estilo

- Español en todo lo visible y en los comentarios.
- Nombres de funciones y variables en español (`ruta`, `destino`, `resumen`).
- Comenta el **por qué**, no el qué.
- Líneas de 88 caracteres como máximo.
- Anotaciones de tipo en las firmas públicas.

## Enviar tu cambio

1. Crea una rama: `git checkout -b agregar-contar-lineas`
2. Haz commits con mensajes claros en español.
3. Comprueba que `pytest` pasa.
4. Abre un pull request explicando qué hace y por qué.

## Licencia

Al contribuir aceptas que tu código se publique bajo la licencia
[MIT](LICENSE) del proyecto. No incluyas código con licencias restrictivas
ni dependencias que no sean libres.
