"""Riesgos climáticos de las fincas con NASA POWER (MERRA-2).

Descarga datos diarios y mensuales de NASA POWER para las tres fincas piloto y
resume lo que el reto pide mirar: calor extremo, lluvia intensa, días secos,
heladas, humedad del suelo de raíz y evapotranspiración. Escribe
``datos/riesgos.json`` y ``datos/riesgos.js`` (snapshot que usa la app sin red).

Uso:
    python3 generar_riesgos.py            # descarga y escribe
    python3 generar_riesgos.py --revisar  # solo comprueba los archivos actuales

Todo es reanálisis: no es un termómetro ni un pluviómetro en la parcela.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

import requests

RAIZ = pathlib.Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
ANIO_INI = 1991
ANIO_FIN = 2025
BASE = (1991, 2020)
RECIENTE = (2021, 2025)
CALOR_C = 35.0
LLUVIA_INTENSA_MM = 20.0
SECO_MM = 1.0
HELADA_C = 2.0
RELLENO = -999.0

URL_DIARIO = "https://power.larc.nasa.gov/api/temporal/daily/point"
URL_MENSUAL = "https://power.larc.nasa.gov/api/temporal/monthly/point"


def pedir(url, finca, parametros, tipo):
    respuesta = requests.get(url, params={
        "community": "AG",
        "latitude": finca["lat"],
        "longitude": finca["lon"],
        "format": "JSON",
        "parameters": parametros,
        "start": str(ANIO_INI),
        "end": str(ANIO_FIN),
    }, timeout=180)
    respuesta.raise_for_status()
    datos = respuesta.json()
    parametros_ok = datos.get("parameters", {})
    return datos["properties"]["parameter"], parametros_ok, tipo


def promedio(valores):
    limpios = [v for v in valores if v is not None and v != RELLENO]
    return sum(limpios) / len(limpios) if limpios else None


def resumir_diario(parametros, anio_ini=ANIO_INI, anio_fin=ANIO_FIN):
    """Cuenta por año los eventos de riesgo a partir del diario de POWER."""
    lluvia = parametros.get("PRECTOTCORR", {})
    tmax = parametros.get("T2M_MAX", {})
    tmin = parametros.get("T2M_MIN", {})
    por_anio = {
        anio: {"lluvia_mm": 0.0, "lluvia_20": 0, "secos": 0, "calor_35": 0,
               "heladas": 0, "lluvia_max": 0.0}
        for anio in range(anio_ini, anio_fin + 1)
    }
    for fecha, mm in lluvia.items():
        if len(fecha) != 8 or mm is None or mm == RELLENO:
            continue
        anio = int(fecha[:4])
        fila = por_anio.get(anio)
        if fila is None:
            continue
        fila["lluvia_mm"] += mm
        fila["lluvia_max"] = max(fila["lluvia_max"], mm)
        if mm >= LLUVIA_INTENSA_MM:
            fila["lluvia_20"] += 1
        if mm < SECO_MM:
            fila["secos"] += 1
    for fecha, valor in tmax.items():
        if len(fecha) != 8 or valor is None or valor == RELLENO:
            continue
        fila = por_anio.get(int(fecha[:4]))
        if fila is not None and valor >= CALOR_C:
            fila["calor_35"] += 1
    for fecha, valor in tmin.items():
        if len(fecha) != 8 or valor is None or valor == RELLENO:
            continue
        fila = por_anio.get(int(fecha[:4]))
        if fila is not None and valor <= HELADA_C:
            fila["heladas"] += 1
    return por_anio


def resumir_mensual(parametros, anio_ini=ANIO_INI, anio_fin=ANIO_FIN):
    """Media mensual de suelo, ET y lluvia en la base y en los últimos años."""
    salida = {}
    for nombre, unidad in (("GWETROOT", "0-1"), ("GWETPROF", "0-1"),
                           ("EVLAND", "mm/día"), ("PRECTOTCORR", "mm/día"),
                           ("T2M", "°C")):
        serie = parametros.get(nombre) or {}
        base, reciente = [], []
        for clave, valor in serie.items():
            if len(clave) != 6 or valor is None or valor == RELLENO:
                continue
            anio, mes = int(clave[:4]), int(clave[4:])
            if mes == 13 or not (anio_ini <= anio <= anio_fin):
                continue
            if BASE[0] <= anio <= BASE[1]:
                base.append(valor)
            elif RECIENTE[0] <= anio <= RECIENTE[1]:
                reciente.append(valor)
        salida[nombre] = {
            "base": redondear(promedio(base), 2 if nombre != "T2M" else 1),
            "reciente": redondear(promedio(reciente), 2 if nombre != "T2M" else 1),
            "unidad": unidad,
        }
        if nombre == "T2M":
            limpios = [v for v in serie.values() if v is not None and v != RELLENO]
            salida[nombre]["minima"] = redondear(min(limpios), 1) if limpios else None
    return salida


def redondear(valor, decimales=1):
    return None if valor is None else round(valor, decimales)


def resumir_anual(por_anio):
    """Compara la media de 1991–2020 con la de 2021–2025 para cada evento."""
    def media(variable, desde, hasta):
        valores = [fila[variable] for anio, fila in por_anio.items() if desde <= anio <= hasta]
        return round(sum(valores) / len(valores), 2) if valores else None

    return {
        "calor_35": {"base": media("calor_35", *BASE), "reciente": media("calor_35", *RECIENTE),
                     "unidad": "días/año"},
        "lluvia_20": {"base": media("lluvia_20", *BASE), "reciente": media("lluvia_20", *RECIENTE),
                      "unidad": "días/año"},
        "secos": {"base": media("secos", *BASE), "reciente": media("secos", *RECIENTE),
                  "unidad": "días/año"},
        "heladas": {"base": media("heladas", *BASE), "reciente": media("heladas", *RECIENTE),
                    "unidad": "días/año"},
        "lluvia_mm": {"base": media("lluvia_mm", *BASE), "reciente": media("lluvia_mm", *RECIENTE),
                      "unidad": "mm/año"},
        "lluvia_max": {"base": media("lluvia_max", *BASE),
                       "reciente": media("lluvia_max", *RECIENTE), "unidad": "mm/día"},
    }


def construir(fincas):
    """Descarga y resume los datos de las fincas. Sin red no hay snapshot."""
    salida = []
    for finca in fincas:
        diario, _meta_d, _ = pedir(URL_DIARIO, finca, "PRECTOTCORR,T2M_MAX,T2M_MIN", "diario")
        mensual, _meta_m, _ = pedir(
            URL_MENSUAL, finca, "GWETROOT,GWETPROF,EVLAND,PRECTOTCORR,T2M", "mensual")
        por_anio = resumir_diario(diario)
        salida.append({
            "id": finca["id"],
            "nombre": finca["nombre"],
            "lat": finca["lat"],
            "lon": finca["lon"],
            "periodo": [ANIO_INI, ANIO_FIN],
            "umbrales": {"calor_c": CALOR_C, "lluvia_intensa_mm": LLUVIA_INTENSA_MM,
                         "seco_mm": SECO_MM, "helada_c": HELADA_C},
            "anual": resumir_anual(por_anio),
            "mensual": resumir_mensual(mensual),
            "por_anio": [{"anio": a, **{k: v for k, v in fila.items()}} for a, fila in sorted(por_anio.items())],
        })
    return {
        "version": 1,
        "generado": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fuente": "NASA POWER (MERRA-2) · daily y monthly · community AG",
        "nota": "Reanálisis: no es un sensor en la parcela. Umbrales de calor/lluvia/helada son de referencia.",
        "fincas": salida,
    }


def escribir(datos):
    DATOS.mkdir(exist_ok=True)
    json.dump(datos, open(DATOS / "riesgos.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    (DATOS / "riesgos.js").write_text(
        "window.__RIESGOS__ = " + json.dumps(datos, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    print(f"escrito datos/riesgos.json ({len(datos['fincas'])} fincas)")


def revisar():
    """Comprueba sin red que el snapshot exista y tenga lo necesario."""
    ruta = DATOS / "riesgos.json"
    if not ruta.exists():
        print("falta datos/riesgos.json: corre python3 generar_riesgos.py")
        return 1
    datos = json.load(open(ruta, encoding="utf-8"))
    faltas = [f["id"] for f in datos.get("fincas", [])
              if not f.get("anual") or not f.get("por_anio")]
    print("OK" if not faltas else f"faltan datos en: {faltas}")
    return 0 if not faltas else 1


def main():
    parser = argparse.ArgumentParser(description="Riesgos climáticos de las fincas (NASA POWER)")
    parser.add_argument("--revisar", action="store_true", help="solo comprueba el snapshot")
    opciones = parser.parse_args()
    if opciones.revisar:
        return revisar()
    fincas = json.load(open(DATOS / "fincas.json", encoding="utf-8"))["fincas"]
    escribir(construir(fincas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
