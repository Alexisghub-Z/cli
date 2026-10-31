# Reparto de tareas

Trabajo en paralelo entre **@Alexisghub-Z** y **@celis23**.

La división sigue las fronteras de los módulos: cada parte toca archivos
distintos, así que podéis trabajar a la vez sin conflictos en Git.

## Estado actual

El alcance de la versión 1 está completo y en `main`:

- 11 herramientas, sistema de permisos, rutas protegidas
- Deshacer universal con papelera propia
- Plan con vista previa para tareas de varios pasos
- 127 pruebas que no dependen del modelo real
- Conjunto de evaluación con 27 tareas en español

**Lo que falta: medirlo con un modelo real y mejorar lo que falle.**

---

## Parte A — @Alexisghub-Z: medición y calidad del modelo

El objetivo es responder a una pregunta que todavía no tiene respuesta:
*¿elige bien las herramientas `qwen3:8b` cuando le hablas en español?*

### A1. Montar Ollama y medir la línea base

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
python evals/ejecutar.py --json resultados-qwen3-8b.json
```

Anota el porcentaje de acierto. **Ese número es la línea base**: todo lo
demás se mide contra él.

### A2. Comparar modelos

```bash
ollama pull qwen2.5:3b
python evals/ejecutar.py --modelo qwen2.5:3b --json resultados-qwen25-3b.json
```

Documenta en el README qué modelo funciona mejor y con cuánta RAM. Es
información que nadie más puede aportar: hace falta ejecutarlo de verdad.

### A3. Mejorar el prompt y las descripciones

Donde la evaluación falle, el problema casi siempre está en uno de dos
sitios:

- `asistente/agent/prompt.py` — el prompt del sistema
- el campo `descripcion` de la herramienta que el modelo confunde

Itera: cambia, vuelve a medir, quédate con lo que sube el porcentaje.

### A4. Ampliar la evaluación

Añade a `evals/tareas.yaml` las peticiones donde el modelo falle en el uso
real. Las tareas que **debe rechazar** son especialmente valiosas.

**Archivos de la parte A:** `evals/`, `asistente/agent/prompt.py`,
descripciones de herramientas, `README.md`.

---

## Parte B — @celis23: herramientas nuevas y robustez

El objetivo es ampliar lo que el asistente sabe hacer, sin tocar el agente.

### B1. Herramienta `comprimir` / `descomprimir`

Estaba en el alcance original y falta. Usa `zipfile` y `tarfile` de la
librería estándar, nada de dependencias nuevas.

- Nivel `CONFIRMACION`, y registra la operación en el diario para deshacer
- Al descomprimir, **verifica que ninguna entrada escape de la carpeta
  destino** (`../` en los nombres: es el ataque *zip slip*).
  `asistente/safety/rutas.py` ya tiene `dentro_de()` para esto
- Pruebas: archivo normal, carpeta, archivo corrupto, e intento de escape

### B2. Herramienta `info_archivo`

Metadatos de un archivo: tamaño, fechas, tipo, permisos. Nivel `LIBRE`.
Es la más sencilla de las dos: buena para empezar y coger el patrón.

### B3. Vista previa de las herramientas nuevas

`asistente/agent/vista_previa.py` tiene una rama por herramienta. Añade la
de `comprimir` y `descomprimir`: cuántos archivos, qué tamaño, dónde van.

### B4. Mensajes de error más claros

Cuando una herramienta falla, el mensaje debería decir **qué hacer**, no
solo qué pasó. Ejemplo: en lugar de «Sin permiso para leer: /x», mejor
«No tengo permiso para leer /x. Prueba con un archivo de tu carpeta
personal». Revisa los `Resultado.error(...)` de `asistente/tools/`.

**Archivos de la parte B:** `asistente/tools/` (archivos nuevos),
`asistente/agent/vista_previa.py`, `tests/`.

---

## Cómo trabajar sin pisarse

```bash
# cada uno en su rama
git checkout -b parte-a-evaluacion     # Alexis
git checkout -b parte-b-herramientas   # Celis
```

1. **No toquéis `asistente/agent/loop.py` ni `asistente/safety/`.** Son el
   núcleo de seguridad y el punto donde sí chocaríais. Si hace falta
   cambiarlos, hablarlo antes.
2. `pytest` tiene que pasar antes de cada push. Son 127 pruebas y tardan
   menos de un segundo: no hay excusa.
3. Al terminar una parte, abre un pull request en lugar de empujar a `main`
   directamente, para que el otro lo revise.
4. Si cambiáis una firma que el otro usa, avisad: el caso más probable es
   el `Confirmador` de `loop.py`, que ya recibe la vista previa.

## Antes de empezar (los dos)

Leed [CONTRIBUTING.md](CONTRIBUTING.md): tiene la guía paso a paso para
agregar una herramienta, con un ejemplo completo que funciona tal cual.
