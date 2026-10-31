"""Mide cuántas tareas del conjunto de evaluación resuelve bien el modelo.

Uso:
    python evals/ejecutar.py                  # usa el modelo de la config
    python evals/ejecutar.py --modelo qwen2.5:3b
    python evals/ejecutar.py --simulado       # comprueba el propio script

Mide solo la *elección de herramienta*: si el modelo entiende la petición
en español y elige la herramienta correcta. No ejecuta nada: el agente se
construye sin confirmador, así que toda acción que requiera permiso se
deniega sola.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from asistente.agent.prompt import prompt_sistema  # noqa: E402
from asistente.config import cargar  # noqa: E402
from asistente.llm.base import ErrorModelo  # noqa: E402
from asistente.llm.ollama import ClienteOllama  # noqa: E402
from asistente.llm.simulado import ClienteSimulado  # noqa: E402
from asistente.tools import cargar_herramientas, registro  # noqa: E402


def cargar_tareas(ruta: Path) -> list[dict]:
    try:
        import yaml
    except ImportError:
        print("Falta PyYAML. Instálalo con: pip install pyyaml")
        raise SystemExit(1)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return datos.get("tareas", [])


def _primera_llamada(cliente, peticion: str):
    """Pide al modelo su primera decisión, sin ejecutar nada."""
    mensajes = [
        {"role": "system", "content": prompt_sistema()},
        {"role": "user", "content": peticion},
    ]
    respuesta = cliente.responder(mensajes, registro.esquemas())
    if not respuesta.llamadas:
        return None, respuesta.texto
    return respuesta.llamadas[0], respuesta.texto


def evaluar_tarea(cliente, tarea: dict) -> dict:
    """Comprueba una tarea y devuelve el resultado."""
    peticion = tarea["peticion"]
    esperada = tarea.get("espera", "")
    prohibidas = set(tarea.get("prohibida", []))

    inicio = time.monotonic()
    try:
        llamada, texto = _primera_llamada(cliente, peticion)
    except ErrorModelo as exc:
        return {
            "peticion": peticion,
            "ok": False,
            "elegida": "",
            "esperada": esperada,
            "motivo": f"error del modelo: {exc}",
            "segundos": round(time.monotonic() - inicio, 1),
        }
    segundos = round(time.monotonic() - inicio, 1)

    elegida = llamada.nombre if llamada else ""
    motivo = ""

    if esperada == "ninguna":
        # Debía negarse: acierta si no propone herramienta.
        ok = llamada is None
        if not ok:
            motivo = f"propuso {elegida} y debía negarse"
    elif elegida in prohibidas:
        ok = False
        motivo = f"usó una herramienta prohibida ({elegida})"
    elif elegida != esperada:
        ok = False
        motivo = f"eligió {elegida or 'ninguna'}"
    else:
        ok = True
        # Si la tarea fija argumentos, se comprueban también.
        for clave, valor in (tarea.get("args_esperados") or {}).items():
            obtenido = llamada.argumentos.get(clave)
            if isinstance(valor, str) and isinstance(obtenido, str):
                coincide = valor.lower() in obtenido.lower()
            else:
                coincide = obtenido == valor
            if not coincide:
                ok = False
                motivo = f"argumento {clave}={obtenido!r}, esperaba {valor!r}"
                break

    return {
        "peticion": peticion,
        "ok": ok,
        "elegida": elegida,
        "esperada": esperada,
        "motivo": motivo,
        "texto": (texto or "")[:120],
        "segundos": segundos,
    }


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--modelo", default="", help="Modelo de Ollama a medir.")
    analizador.add_argument(
        "--simulado",
        action="store_true",
        help="Usa un modelo simulado que siempre acierta (prueba el script).",
    )
    analizador.add_argument(
        "--json", default="", help="Guarda el detalle en este archivo JSON."
    )
    args = analizador.parse_args()

    cargar_herramientas()
    tareas = cargar_tareas(Path(__file__).parent / "tareas.yaml")

    if args.simulado:
        cliente = _ClienteQueAcierta(tareas)
        etiqueta = "simulado"
    else:
        config = cargar()
        modelo = args.modelo or config.modelo
        cliente = ClienteOllama(
            modelo=modelo, host=config.host, temperatura=config.temperatura
        )
        disponible, aviso = cliente.disponible()
        if not disponible:
            print(f"No puedo evaluar: {aviso}")
            return 1
        etiqueta = modelo

    print(f"Evaluando «{etiqueta}» con {len(tareas)} tareas...\n")

    resultados = []
    for indice, tarea in enumerate(tareas, start=1):
        resultado = evaluar_tarea(cliente, tarea)
        resultados.append(resultado)
        marca = "✓" if resultado["ok"] else "✗"
        print(f"{marca} [{indice:2}/{len(tareas)}] {resultado['peticion'][:58]}")
        if not resultado["ok"]:
            print(f"      → {resultado['motivo']}")

    aciertos = sum(1 for r in resultados if r["ok"])
    porcentaje = aciertos / len(resultados) * 100 if resultados else 0.0
    tiempo = sum(r["segundos"] for r in resultados)

    print(f"\n{'─' * 60}")
    print(f"Modelo:    {etiqueta}")
    print(f"Aciertos:  {aciertos}/{len(resultados)} ({porcentaje:.0f}%)")
    print(f"Tiempo:    {tiempo:.0f}s en total")

    fallos = [r for r in resultados if not r["ok"]]
    if fallos:
        print(f"\nFalló en {len(fallos)}:")
        for fallo in fallos:
            print(f"  · {fallo['peticion'][:50]}: {fallo['motivo']}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "modelo": etiqueta,
                    "aciertos": aciertos,
                    "total": len(resultados),
                    "porcentaje": round(porcentaje, 1),
                    "resultados": resultados,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nDetalle en {args.json}")

    return 0 if aciertos == len(resultados) else 2


class _ClienteQueAcierta(ClienteSimulado):
    """Modelo simulado que responde lo esperado: valida el propio script."""

    def __init__(self, tareas: list[dict]) -> None:
        super().__init__()
        self._por_peticion = {t["peticion"]: t for t in tareas}

    def responder(self, mensajes, herramientas=None):
        peticion = mensajes[-1]["content"]
        tarea = self._por_peticion.get(peticion, {})
        esperada = tarea.get("espera", "")
        if not esperada or esperada == "ninguna":
            return ClienteSimulado.con_texto("No puedo hacer eso.")
        return ClienteSimulado.con_herramienta(
            esperada, **(tarea.get("args_esperados") or {})
        )


if __name__ == "__main__":
    raise SystemExit(main())
