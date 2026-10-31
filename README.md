# Asistente de terminal con IA local

Asistente de línea de comandos que usa un modelo de IA de **pesos abiertos
corriendo en tu computadora** (sin internet, sin enviar tus archivos a ningún
servidor) para hacer tareas a partir de instrucciones en español.

```
› ¿qué hay en mi carpeta de descargas?
› organiza mis descargas por tipo de archivo
› ¿qué está ocupando más espacio en mi disco?
```

> **Estado:** en desarrollo. Ya funciona de punta a punta el bucle del agente,
> el sistema de permisos y la herramienta `listar_directorio`. Las demás
> herramientas y el comando `deshacer` están en camino (ver [Hoja de ruta](#hoja-de-ruta)).

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
pytest
```

Las pruebas **no dependen del modelo real**: usan `ClienteSimulado`, que
devuelve respuestas predefinidas. Se ejecutan en menos de un segundo y no
necesitan que Ollama esté instalado.

## Hoja de ruta

- [x] Cliente del modelo (Ollama + simulado) e interfaz abstracta
- [x] Sistema de permisos y rutas protegidas
- [x] Bucle del agente con límite de pasos y detección de ciclos
- [x] `listar_directorio`
- [ ] `buscar_archivos`, `leer_archivo`
- [ ] `mover`, `copiar`, `renombrar`, `crear_carpeta`
- [ ] `enviar_a_papelera` (reversible)
- [ ] `espacio_en_disco`, `procesos`
- [ ] `ejecutar_comando` (siempre con confirmación)
- [ ] Deshacer universal (`asistente deshacer`)
- [ ] Plan y vista previa en tareas de varios pasos
- [ ] Conjunto de evaluación con 20+ tareas en español

Más adelante: recetas reutilizables, memoria de preferencias, sistema de
plugins, herramienta de cámara con modelo de visión.

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md); incluye una guía paso a paso para
**agregar una herramienta nueva**.

## Licencia

[MIT](LICENSE). Todas las dependencias son libres (MIT o BSD) y el modelo por
defecto es Apache 2.0.
