"""Genera ``datos/rotaciones.json`` y su espejo ``datos/rotaciones.js``.

Lee la climatología POWER de ``datos/fincas.json`` (tarea 1) y, si existe, el
bloque de temporada de ``datos/reciente.json`` (tarea 2). Si existe
``datos/cultivos.json`` (tarea 8), lo usa en lugar de la tabla provisional del
motor.

Uso::

    python generar_rotaciones.py
    python generar_rotaciones.py --verificar

``--verificar`` calcula e imprime el resumen sin escribir nada.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.rotaciones import evaluar_rotaciones

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
FINCAS = DATOS / "fincas.json"
RECIENTE = DATOS / "reciente.json"
CULTIVOS = DATOS / "cultivos.json"
SUELO = DATOS / "suelo.json"
SALIDA_JSON = DATOS / "rotaciones.json"
SALIDA_JS = DATOS / "rotaciones.js"

FUENTE_CLIMA = "NASA POWER (reanálisis MERRA-2)"


def _leer(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _por_id(documento):
    """``{id: bloque}`` de un documento con la lista ``fincas``."""
    bloques = {}
    for bloque in (documento or {}).get("fincas") or []:
        if isinstance(bloque, dict) and bloque.get("id"):
            bloques[bloque["id"]] = bloque
    return bloques


def _tabla_cultivos(documento):
    """``{id: cultivo}`` de ``datos/cultivos.json``, o ``None`` si no aplica."""
    if not documento:
        return None
    cultivos = documento.get("cultivos")
    if not cultivos:
        return None
    return {
        cultivo["id"]: cultivo
        for cultivo in cultivos
        if isinstance(cultivo, dict) and cultivo.get("id")
    }


def construir(fincas_documento, reciente_documento=None, cultivos_documento=None,
              suelo_documento=None, ahora=None):
    """Documento de rotaciones a partir de los snapshots del repo."""
    fincas = (fincas_documento or {}).get("fincas") or []
    recientes = _por_id(reciente_documento)
    suelos = _por_id(suelo_documento)
    cultivos = _tabla_cultivos(cultivos_documento)

    momento = ahora or datetime.now().astimezone()
    return {
        "version": 1,
        "generado": momento.isoformat(timespec="seconds"),
        "fuente_clima": FUENTE_CLIMA,
        "fuente_suelo": "ISRIC SoilGrids 2.0 (CC BY 4.0)" if suelos else None,
        "fincas": [
            evaluar_rotaciones(
                finca,
                contexto_reciente=recientes.get(finca.get("id")),
                cultivos=cultivos,
                suelo=suelos.get(finca.get("id")),
            )
            for finca in fincas
        ],
    }


def _imprimir(documento):
    fincas = documento.get("fincas") or []
    print(f"{len(fincas)} fincas")
    for finca in fincas:
        secos = ", ".join(str(mes) for mes in finca.get("meses_secos") or [])
        indices = " · ".join(
            f"{estrategia['id']} {estrategia['indice']}"
            for estrategia in finca.get("estrategias") or []
        )
        print(f"{finca.get('id')}: meses secos {secos or 'sin dato'} · {indices}")


def _escribir(ruta, texto):
    """Escritura atómica: archivo temporal en el mismo directorio y replace."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(texto, encoding="utf-8")
    os.replace(temporal, ruta)


def main(argv=None):
    analizador = argparse.ArgumentParser(
        description="Genera las rotaciones por finca a partir de datos/fincas.json"
    )
    analizador.add_argument(
        "--verificar",
        action="store_true",
        help="calcula e imprime el resumen sin escribir los archivos",
    )
    argumentos = analizador.parse_args(argv)

    if not FINCAS.exists():
        print(
            "Falta datos/fincas.json (tarea 1). No se pueden generar las "
            "rotaciones.",
            file=sys.stderr,
        )
        return 2

    fincas_documento = _leer(FINCAS)
    reciente_documento = _leer(RECIENTE) if RECIENTE.exists() else None
    cultivos_documento = _leer(CULTIVOS) if CULTIVOS.exists() else None
    suelo_documento = _leer(SUELO) if SUELO.exists() else None

    documento = construir(
        fincas_documento,
        reciente_documento=reciente_documento,
        cultivos_documento=cultivos_documento,
        suelo_documento=suelo_documento,
    )

    if argumentos.verificar:
        _imprimir(documento)
        return 0

    _escribir(
        SALIDA_JSON,
        json.dumps(documento, ensure_ascii=False, indent=1) + "\n",
    )
    _escribir(
        SALIDA_JS,
        "window.__ROTACIONES__ = "
        + json.dumps(documento, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
    )
    _imprimir(documento)
    print(f"Escrito {SALIDA_JSON.relative_to(RAIZ)} y {SALIDA_JS.relative_to(RAIZ)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
