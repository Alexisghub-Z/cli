# Asistente de terminal con IA local

Asistente de línea de comandos que usa un modelo de IA de **pesos abiertos
corriendo en tu computadora** (sin internet, sin enviar tus archivos a ningún
servidor) para hacer tareas a partir de instrucciones en español.

```
› ¿qué hay en mi carpeta de descargas?
› organiza mis descargas por tipo de archivo
› ¿qué está ocupando más espacio en mi disco?
```

> **Estado:** el alcance de la versión 1 está completo — 14 herramientas,
> deshacer universal, plan con vista previa, recetas y 204 pruebas.
>
> **Medido con modelo real:** `qwen2.5:3b` acierta el **94.4%** de las 36
> tareas de evaluación (ver [Resultados](#resultados-de-la-evaluación)).
> `qwen3:8b` sigue sin medir.

## Por qué este y no otro

1. **Seguridad primero.** El modelo nunca ejecuta nada. Solo *propone* acciones
   estructuradas; el agente las valida y decide según un sistema de permisos.
2. **Deshacer universal.** Antes de modificar archivos se guarda un respaldo,
   para revertir cualquier acción con `asistente deshacer`.
3. **Plan antes de actuar.** En tareas de varios pasos muestra el plan y una
   vista previa antes de ejecutar.
4. **Hardware modesto.** Diseñado para modelos de 3B–8B parámetros.
5. **Español nativo.** Mensajes, ayuda y prompts del sistema en español.

## Requisitos

- **Python 3.11 o superior**
- **[Ollama](https://ollama.com)** instalado y corriendo
- **~6 GB de RAM libre** para el modelo por defecto (`qwen3:8b`)

## Instalación

```bash
# 1. Clona el repositorio
git clone https://github.com/Alexisghub-Z/cli.git
cd cli

# 2. Crea un entorno virtual
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate

# 3. Instala el asistente
pip install -e ".[dev]"

# 4. Descarga el modelo (solo la primera vez, ~5 GB)
ollama pull qwen3:8b
```

Comprueba que todo está en su sitio:

```bash
asistente herramientas     # lista las herramientas y sus permisos
asistente config           # muestra la configuración activa
```

## Uso

**Una sola petición:**

```bash
asistente pedir "qué hay en mi carpeta de descargas"
```

**Modo interactivo:**

```bash
asistente            # o: asistente charlar
› ¿cuántos archivos PDF tengo en Documentos?
› salir
```

**Recetas** — guarda una tarea que salió bien y repítela:

```bash
asistente pedir "crea una carpeta PDF en Descargas y mueve ahí los pdf"
asistente receta guardar "organizar pdf" --descripcion "ordena las descargas"
asistente receta listar
asistente receta ejecutar "organizar pdf"
asistente receta borrar "organizar pdf"
```

Una receta guarda **nombres de herramienta y parámetros**, nunca comandos de
shell: al reproducirla vuelve a pasar por el sistema de permisos, igual que si
la pidiera el modelo. Una receta que apunte a una ruta protegida se bloquea.

Los parámetros admiten huecos con `{nombre}`, que se rellenan al ejecutar:

```json
{"herramienta": "crear_carpeta", "argumentos": {"ruta": "{carpeta}/PDF"}}
```

```bash
asistente receta ejecutar "organizar pdf" --dato carpeta=~/Documentos
```

Si falta un dato, se pide por teclado. Reproducir una receta **no necesita el
modelo**: son llamadas directas a las herramientas, así que funciona sin Ollama.

**Deshacer:**

```bash
asistente deshacer --listar    # qué se puede revertir
asistente deshacer             # revierte la última operación
asistente deshacer --todo      # revierte todas las pendientes
asistente papelera             # qué hay en la papelera
```

### Herramientas disponibles

| Herramienta | Permiso | Qué hace |
|---|---|---|
| `listar_directorio` | libre | lista archivos y carpetas |
| `info_archivo` | libre | tamaño, tipo, fechas y permisos |
| `buscar_archivos` | libre | busca por nombre, extensión, tamaño o fecha |
| `leer_archivo` | libre | lee texto (detecta binarios, bloquea rutas sensibles) |
| `espacio_en_disco` | libre | espacio total, usado y libre |
| `procesos` | libre | procesos que más memoria consumen |
| `mover` | confirmación | mueve sin pisar el destino |
| `copiar` | confirmación | copia dejando el original |
| `renombrar` | confirmación | solo el nombre, no la ruta |
| `crear_carpeta` | confirmación | crea carpetas intermedias |
| `enviar_a_papelera` | confirmación | reversible; sustituye al borrado |
| `comprimir` | confirmación | empaqueta en ZIP |
| `descomprimir` | confirmación | extrae ZIP y TAR, con defensa *zip slip* |
| `ejecutar_comando` | confirmación | shell, con el comando a la vista |

`asistente herramientas` las lista en cualquier momento.

## El modelo

Por defecto usa **`qwen3:8b`**, elegido por dos razones:

- **Licencia Apache 2.0**, aprobada por la OSI: software libre de verdad, sin
  límites de uso ni cláusulas especiales.
- Es de los modelos pequeños más fiables en *tool calling* (llamada a
  herramientas), que es lo que este asistente necesita.

> ⚠️ **Nota para quien cambie el modelo por defecto:** evita Llama y Gemma.
> Aunque son buenos modelos, sus licencias **no son open source** (la de Llama
> exige permiso de Meta por encima de 700M de usuarios activos, obliga a poner
> "Built with Llama" y prohíbe usar sus salidas para mejorar otros modelos).
> La familia Qwen tampoco tiene licencia uniforme: el 8B es Apache 2.0, pero
> algunos checkpoints usan licencias propias. Verifica antes de cambiarlo.

### Si tu computadora tiene poca RAM

Un modelo 8B necesita unos 6 GB libres. Con menos, usa un modelo de 3B:

```bash
ollama pull qwen2.5:3b
```

Y en el archivo de configuración (`asistente config --crear` te dice dónde
está) cambia:

```toml
modelo = "qwen2.5:3b"
```

### Otro backend

El cliente del modelo está detrás de la interfaz abstracta `ClienteLLM`
(`asistente/llm/base.py`), así que añadir llama.cpp u otro backend es
implementar dos métodos. No hay que tocar el agente.

## Niveles de permiso

| Nivel | Qué incluye | Comportamiento |
|---|---|---|
| **Libre** | leer, listar, buscar, info del sistema | se ejecuta directamente |
| **Con confirmación** | crear, mover, copiar, renombrar, comprimir, ejecutar comandos | te muestra la acción exacta y pide permiso |
| **Bloqueado** | borrado permanente, `sudo`, rutas protegidas | nunca se ejecuta |

Las **rutas protegidas** (archivos del sistema como `/etc` o `C:\Windows`, y
configuración sensible como `~/.ssh`, `~/.gnupg`, `~/.aws`) están bloqueadas
**incluso si tú confirmas la acción**, y la comprobación resuelve los enlaces
simbólicos, así que un enlace con nombre inocente que apunte a `/etc` tampoco
pasa.

Además, `ejecutar_comando` rechaza antes de ejecutar:

- escalada de privilegios: `sudo`, `su`, `doas`, `pkexec`, `runas`
- borrado sin vuelta atrás: `rm -rf`, `shred`
- operaciones de disco: `mkfs`, `dd of=`, `fdisk`
- código descargado: `curl … | bash`
- apagado del sistema y bombas de bifurcación

La comprobación revisa **cada tramo** del comando, así que `ls && sudo reboot`
también se rechaza. Y `leer_archivo` se niega a leer configuración sensible,
para que el modelo no pueda ver tus claves privadas.

Al descomprimir, cada entrada del archivo se verifica **antes** de extraer
nada: un ZIP o TAR puede traer nombres como `../../.ssh/authorized_keys` para
escribir fuera de la carpeta destino (ataque *zip slip*). Se rechazan rutas
absolutas, `..`, unidades de Windows y enlaces que apunten fuera; si una sola
entrada es sospechosa, no se extrae nada.

### Plan antes de actuar

En tareas de varios pasos («organiza mis descargas por tipo»), el asistente
no va ejecutando acciones de una en una: propone el plan completo con la
vista previa de cada cambio y lo apruebas **una sola vez**.

```
╭────────────────────── Plan propuesto (3 pasos) ──────────────────────╮
│ Organizar las descargas por tipo de archivo                          │
│                                                                      │
│ 1. crear_carpeta — carpeta para las fotos                            │
│    + Nueva carpeta: ~/Descargas/Imagenes                             │
│                                                                      │
│ 2. mover — mover la foto                                             │
│    → ~/Descargas/foto.jpg → ~/Descargas/Imagenes                     │
│    - foto.jpg dejará de estar en ~/Descargas                          │
╰──────────────────────────────────────────────────────────────────────╯
¿Ejecuto este plan? [y/n]
```

Los símbolos indican el tipo de cambio: `+` crear, `~` modificar, `→` mover,
`-` eliminar, `$` ejecutar. La vista previa avisa cuando el destino ya existe
y cuando un paso **no se podrá deshacer**.

Un plan se valida **entero antes de mostrarse**: si algún paso toca una ruta
protegida o tiene parámetros inválidos, no se te ofrece como viable. Si un
paso falla durante la ejecución, el plan se detiene ahí en lugar de seguir
con pasos que dependían de él.

### Deshacer

Toda operación que modifica archivos se registra en un diario (JSONL, texto
legible) con lo necesario para revertirla. `enviar_a_papelera` mueve a una
papelera propia del asistente en lugar de borrar, así que se puede recuperar.
Al deshacer la creación de una carpeta, si ya tiene archivos dentro el
asistente se niega a borrarla.

## Arquitectura

```
asistente/
├── cli/        punto de entrada: modo un-comando y REPL
├── agent/      bucle: pensar → elegir → validar → permiso → ejecutar → observar
├── llm/        cliente del modelo (interfaz abstracta + Ollama + simulado)
├── tools/      una clase por herramienta + registro central
├── safety/     niveles de permiso y rutas protegidas
└── undo/       diario de operaciones y respaldos
```

La decisión de seguridad **no vive dentro de las herramientas**, sino en el
bucle del agente, que consulta `safety/` antes de llamar a `run()`. Así una
herramienta mal escrita no puede saltarse los permisos por olvido.

El bucle tiene un **límite de pasos** (8 por defecto) y además detecta cuando
el modelo repite la misma llamada sin avanzar, para no entrar en ciclos.

## Pruebas

```bash
pytest          # 204 pruebas, menos de un segundo
```

Las pruebas **no dependen del modelo real**: usan `ClienteSimulado`, que
devuelve respuestas predefinidas. No necesitan que Ollama esté instalado.

## Evaluación

Para medir si el modelo entiende las peticiones en español y elige bien la
herramienta, hay un conjunto de 27 tareas:

```bash
python evals/ejecutar.py                      # con el modelo configurado
python evals/ejecutar.py --modelo qwen2.5:3b  # comparar modelos
python evals/ejecutar.py --json salida.json   # guardar el detalle
```

Incluye tareas que el asistente **debe rechazar** (tocar `/etc`, leer tu clave
SSH) y tareas donde debe preferir la herramienta segura al comando de shell.
La evaluación no ejecuta nada: solo mide qué herramienta elegiría.

### Resultados de la evaluación

| Modelo | Aciertos | Cuándo |
|---|---|---|
| `qwen2.5:3b` | 32/36 (88.9%) | antes de ajustar las descripciones |
| `qwen2.5:3b` | **34/36 (94.4%)** | después de ajustarlas |
| `qwen3:8b` | sin medir | hace falta una máquina con 16 GB |

Los datos crudos están en `evals/resultados/`. La lección más útil: **cuando
el modelo falla, el problema casi siempre está en la descripción de la
herramienta, no en el prompt del sistema.** Subir del 88.9% al 94.4% fue
cuestión de separar las descripciones que se solapaban y añadir referencias
cruzadas («para leer el contenido usa leer_archivo»).

El fallo más instructivo: con «elimina esa carpeta que ya no uso», el modelo
elegía `mover` en lugar de `enviar_a_papelera`. Es el peor caso posible,
porque `mover` también modifica archivos: el usuario podía aprobar un
desplazamiento creyendo que desechaba algo. Se corrigió haciendo que
`enviar_a_papelera` reclame los verbos «eliminar» y «borrar», y que `mover`
diga explícitamente que no sirve para eso.

`tests/test_descripciones.py` protege esas distinciones sin necesidad del
modelo, para que no se pierdan al editar una descripción más adelante.

## Hoja de ruta

- [x] Cliente del modelo (Ollama + simulado) e interfaz abstracta
- [x] Sistema de permisos y rutas protegidas
- [x] Bucle del agente con límite de pasos y detección de ciclos
- [x] `listar_directorio`
- [x] `buscar_archivos`, `leer_archivo`
- [x] `mover`, `copiar`, `renombrar`, `crear_carpeta`
- [x] `enviar_a_papelera` (reversible)
- [x] `espacio_en_disco`, `procesos`
- [x] `ejecutar_comando` (siempre con confirmación)
- [x] Deshacer universal (`asistente deshacer`)
- [x] Conjunto de evaluación con 27 tareas en español
- [x] Plan y vista previa en tareas de varios pasos
- [ ] Medir la evaluación con un modelo real

- [x] Recetas: guardar una tarea exitosa y repetirla

Más adelante: memoria de preferencias, sistema de plugins, herramienta de
cámara con modelo de visión.

## Probar a mano

Las pruebas automáticas usan un modelo simulado, así que confirman que el
código funciona pero no que el modelo entienda bien el español. Para probarlo
de verdad con Ollama hay una guía paso a paso en [PROBAR.md](PROBAR.md), con
un campo de pruebas de juguete para no tocar tus archivos reales.

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md); incluye una guía paso a paso para
**agregar una herramienta nueva**.

## Licencia

[MIT](LICENSE). Todas las dependencias son libres (MIT o BSD) y el modelo por
defecto es Apache 2.0.
