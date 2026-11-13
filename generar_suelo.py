"""Suelo de cada finca desde ISRIC SoilGrids 2.0 (API abierta, sin clave).

Escribe ``datos/suelo.json`` y su espejo ``datos/suelo.js``. Una petición por
finca con las cuatro propiedades: el servidor tarda ~70 s, así que usa un
timeout largo, reintenta y deja ``null`` lo que no llegue.

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
ESPERA = 5.0
TIMEOUT = 150
# El valor "mean" viene con d_factor 10: g/kg -> %, pH*10 -> pH, dg/kg -> g/kg.
FACTOR = {"clay": 10.0, "sand": 10.0, "soc": 10.0, "phh2o": 10.0}


def _pedir(lat, lon):
    """Una petición con las cuatro propiedades. Devuelve {propiedad: valor}."""
    propiedades = "".join(f"&property={p}" for p in PROPIEDADES)
    url = f"{URL}?lon={lon}&lat={lat}{propiedades}&depth={PROFUNDIDAD}&value=mean"
    for intento in range(REINTENTOS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as respuesta:
                datos = json.load(respuesta)
            fila = {p: None for p in PROPIEDADES}
            for capa in datos["properties"]["layers"]:
                valor = capa["depths"][0]["values"]["mean"]
                if valor is not None:
                    fila[capa["name"]] = round(valor / FACTOR[capa["name"]], 2)
            return fila
        except Exception:  # servidor lento o 500: reintenta
            print(f"reintento {intento + 1}...", end=" ", flush=True)
            if intento < REINTENTOS - 1:
                time.sleep(ESPERA * (intento + 1))
    return {p: None for p in PROPIEDADES}


def construir(lat, lon):
    return _pedir(lat, lon)


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
    previo = {}
    ruta_previa = DATOS / "suelo.json"
    if ruta_previa.exists():
        try:
            for f in json.loads(ruta_previa.read_text(encoding="utf-8")).get("fincas", []):
                previo[f["id"]] = f
        except (ValueError, KeyError):
            previo = {}

    for finca in fincas:
        print(f"  {finca['id']}...", end=" ", flush=True)
        antes = previo.get(finca["id"], {})
        if all(v is not None for v in (antes.get("arcilla_pct"), antes.get("arena_pct"),
                                       antes.get("carbono_organico_g_kg"), antes.get("ph"))):
            salida["fincas"].append(antes)
            print("ya estaba")
            continue
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
