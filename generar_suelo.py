"""Suelo de cada finca desde ISRIC SoilGrids 2.0 (API abierta, sin clave).

Escribe ``datos/suelo.json`` y su espejo ``datos/suelo.js``. Una petición por
propiedad porque el servidor devuelve 500 al pedir varias a la vez; es lento,
así que reintenta y deja ``null`` lo que no llegue.

Uso:
    python3 generar_suelo.py            # escribe (usa la red)
    python3 generar_suelo.py --verificar  # imprime sin escribir
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPIEDADES = ("clay", "sand", "soc", "phh2o")
PROFUNDIDAD = "0-5cm"
REINTENTOS = 3
ESPERA = 3.0
TIMEOUT = 90
# Factor de SoilGrids: el valor "mean" va en las unidades mapeadas tras dividir.
FACTOR = {"clay": 10.0, "sand": 10.0, "soc": 10.0, "phh2o": 10.0}


def _pedir(lat, lon, propiedad):
    url = (f"{URL}?lon={lon}&lat={lat}&property={propiedad}"
           f"&depth={PROFUNDIDAD}&value=mean")
    for intento in range(REINTENTOS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as respuesta:
                datos = json.load(respuesta)
            capa = datos["properties"]["layers"][0]
            valor = capa["depths"][0]["values"]["mean"]
            if valor is None:
                return None
            return round(valor / FACTOR[propiedad], 2)
        except Exception:  # servidor lento o 500: reintenta
            if intento < REINTENTOS - 1:
                time.sleep(ESPERA * (intento + 1))
    return None


def construir(lat, lon):
    fila = {}
    for propiedad in PROPIEDADES:
        fila[propiedad] = _pedir(lat, lon, propiedad)
        time.sleep(1.0)
    return fila


def textura(clay, sand):
    """Clase textural simplificada (USDA) a partir de arcilla y arena en %.
    shortcut: reglas de 4 tramos, no el triángulo USDA completo."""
    if clay is None or sand is None:
        return None
    if clay >= 40:
        return "arcilloso"
    if sand >= 70:
        return "arenoso"
    if clay >= 27:
        return "franco-arcilloso"
    if sand >= 50:
        return "franco-arenoso"
    return "franco"


def main():
    fincas = json.loads((DATOS / "fincas.json").read_text(encoding="utf-8"))["fincas"]
    salida = {"version": 1, "fuente": "ISRIC SoilGrids 2.0 (CC BY 4.0)",
              "profundidad": PROFUNDIDAD, "actualizado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "avisos": [], "fincas": []}
    for finca in fincas:
        print(f"  {finca['id']}...", end=" ", flush=True)
        fila = construir(finca["lat"], finca["lon"])
        faltan = [k for k, v in fila.items() if v is None]
        if faltan:
            salida["avisos"].append(
                f"{finca['id']}: sin dato de {', '.join(faltan)} (servidor lento).")
        salida["fincas"].append({
            "id": finca["id"],
            "arcilla_pct": fila["clay"],
            "arena_pct": fila["sand"],
            "carbono_organico_g_kg": fila["soc"],
            "ph": fila["phh2o"],
            "textura": textura(fila["clay"], fila["sand"]),
        })
        print("ok" if not faltan else f"parcial ({', '.join(faltan)} vacío)")
    if "--verificar" in sys.argv:
        print(json.dumps(salida, ensure_ascii=False, indent=1)[:800])
        return 0
    texto = json.dumps(salida, ensure_ascii=False, indent=1)
    temporal = DATOS / "suelo.json.tmp"
    temporal.write_text(texto, encoding="utf-8")
    os.replace(temporal, DATOS / "suelo.json")
    (DATOS / "suelo.js").write_text(
        "window.__SUELO__ = " + json.dumps(salida, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    print("escrito: datos/suelo.json y datos/suelo.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
