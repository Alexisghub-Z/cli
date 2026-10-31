# Reparto de tareas

Trabajo en paralelo entre **@Alexisghub-Z**, **@celis23** y
**@MonserratLazaro**.

La división sigue las fronteras de los módulos: cada parte toca archivos
distintos, así que podéis trabajar a la vez sin conflictos en Git.

| Quién | Parte | Qué mide o construye |
|---|---|---|
| **@celis23** | A — medición automática | cuántas veces el modelo acierta la herramienta |
| **@Alexisghub-Z** | B — herramientas nuevas | amplía lo que el asistente sabe hacer |
| **@MonserratLazaro** | C — prueba manual con Ollama | si usarlo de verdad resulta claro y seguro |

**A y C no se solapan**, aunque las dos usen Ollama. La evaluación de A mide
el acierto sobre 36 peticiones fijas; la prueba de C mira la experiencia de
uso: si los mensajes se entienden, si la vista previa es clara, si en algún
caso se salta una confirmación. Un 94% de acierto es compatible con una
experiencia mala, así que hacen falta las dos.

## Estado actual

El alcance de la versión 1 está completo y en `main`:

- 11 herramientas, sistema de permisos, rutas protegidas
- Deshacer universal con papelera propia
- Plan con vista previa para tareas de varios pasos
- 127 pruebas que no dependen del modelo real
- Conjunto de evaluación con 27 tareas en español

**Lo que falta: medirlo con un modelo real y mejorar lo que falle.**

---

## Parte A — @celis23: medición y calidad del modelo

El objetivo es responder a una pregunta que todavía no tiene respuesta:
*¿elige bien las herramientas `qwen3:8b` cuando le hablas en español?*

> **Esta parte necesita una máquina con al menos 16 GB de RAM.** Un modelo
> 8B cuantizado ocupa unos 5 GB solo de pesos; por debajo de ~8 GB libres el
> sistema empieza a usar swap y cada respuesta tarda minutos en lugar de
> segundos. Sin GPU todo corre en CPU, así que cuenta con 10–30 segundos por
> respuesta: es normal, no es un fallo.
>
> Si la máquina no da para el 8B, mide `qwen2.5:3b` (~2 GB) y dilo en el
> informe: comparar los dos es justamente el punto A2.

> Para probar el asistente a mano con un modelo real, sigue
> [PROBAR.md](PROBAR.md): tiene los pasos, un campo de pruebas de juguete y
> la lista de lo que debe rechazarse por seguridad.

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

## Parte B — @Alexisghub-Z: herramientas nuevas y robustez

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
git checkout -b parte-a-evaluacion     # Celis
git checkout -b parte-b-herramientas   # Alexis
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

## Dónde se tocan las partes

Las tres son independientes **salvo en un punto**: cuando A o C descubren que
el modelo confunde dos herramientas, la solución está en el campo
`descripcion` de esa herramienta, que es territorio de la parte B.

Cuando pase, abrid un issue con la petición exacta, qué herramienta eligió el
modelo y cuál esperabais, en vez de editar el archivo de otra persona.

Ya ocurrió una vez y funcionó bien: @celis23 midió que «elimina esa carpeta»
elegía `mover` en lugar de `enviar_a_papelera`, y el arreglo fue reescribir
las dos descripciones.

---

## Parte C — @MonserratLazaro: prueba manual con Ollama

Sigue [PROBAR.md](PROBAR.md), que tiene los pasos completos. En resumen:

### C1. Montar y probar

Instala Ollama y el asistente, crea el campo de pruebas de juguete que indica
la guía (**no pruebes sobre tus archivos reales**) y recorre las listas de
comprobación: consultas, acciones con confirmación, planes de varios pasos,
deshacer, recetas y modo interactivo.

### C2. Seguridad

La guía lista cinco peticiones que **deben** rechazarse (`/etc`, la clave SSH,
`sudo rm -rf /`...) y el caso más sutil: una ruta protegida debe bloquearse
**aunque tú apruebes la acción**.

Si alguna se ejecuta, es un fallo grave: abre un issue de inmediato.

### C3. Anotar lo que chirríe

Lo que buscamos no es solo «funciona o no», sino:

- mensajes que no se entiendan
- vistas previas que no dejen claro qué va a pasar
- respuestas en inglés (fallo del prompt del sistema)
- tiempos de espera incómodos
- cualquier caso donde el asistente actúe sin pedir permiso

Abre un issue por cada cosa, con la petición exacta, qué herramienta eligió,
qué esperabas y qué modelo usabas.

**Archivos de la parte C:** issues y, si hace falta, `PROBAR.md`. No necesita
tocar código.

### Si encuentras un fallo del modelo

Cuando el modelo elige mal una herramienta, el arreglo suele estar en el campo
`descripcion` de esa herramienta, que es territorio de la parte B. Abre un
issue en vez de editarlo: así @Alexisghub-Z lo arregla con las pruebas de
`tests/test_descripciones.py` delante.
