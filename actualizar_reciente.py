"""Actualiza `datos/reciente.json` y `datos/reciente.js` con Open-Meteo.

Lee las fincas de `datos/fincas.json` (tarea 1), pide a Open-Meteo los últimos
30 días + 7 de pronóstico y la normal 1991–2020 de ERA5 (misma fuente), y
escribe el snapshot que muestra la interfaz. La lógica de cálculo vive en
`tools/reciente.py`; aquí solo hay red, archivos y consola.

Uso:
    python actualizar_reciente.py                     # con red
    python actualizar_reciente.py --sin-red           # fixtures, sin red
    python actualizar_reciente.py --recalcular-climatologia

Códigos de salida: 0 correcto, 1 sin conexión (se conserva la caché),
2 falta `datos/fincas.json`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from tools.reciente import (
    DIAS_PRONOSTICO,
    construir_climatologia,
    construir_reciente,
    escribir_atomico,
    leer_cache,
)

RECIENTE_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVO_URL = "https://archive-api.open-meteo.com/v1/archive"
AGENTE = "tierra/1.0"
ESPERA = 30
ANIO_INI = 1991
ANIO_FIN = 2020

FINCAS = os.path.join("datos", "fincas.json")
CLIMATOLOGIA = os.path.join("datos", "climatologia_era5.json")
SALIDA_JSON = os.path.join("datos", "reciente.json")
SALIDA_JS = os.path.join("datos", "reciente.js")
FIXTURES = os.path.join("tests", "fixtures")

# Los fixtures se llaman como los archivos que pide el contrato de la tarea 2.
FIXTURES_POR_FINCA = {
    "constanza": "openmeteo_constanza.json",
    "azua": "openmeteo_azua.json",
    "san_francisco_de_macoris": "openmeteo_sfm.json",
}

ZONA_POR_DEFECTO = "America/Santo_Domingo"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# Red
# --------------------------------------------------------------------------

def _pedir_json(url, parametros):
    """GET con ``urllib`` y mensajes en español; lanza ``RuntimeError``."""
    consulta = urllib.parse.urlencode(parametros, doseq=True)
    peticion = urllib.request.Request(
        f"{url}?{consulta}",
        headers={"User-Agent": AGENTE, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:
            cuerpo = respuesta.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Open-Meteo respondió HTTP {error.code}") from None
    except urllib.error.URLError as error:
        motivo = getattr(error, "reason", error)
        raise RuntimeError(f"sin conexión a Open-Meteo ({motivo})") from None
    except TimeoutError:
        raise RuntimeError("tiempo de espera agotado al consultar Open-Meteo") from None
    try:
        return json.loads(cuerpo.decode("utf-8"))
    except ValueError:
        raise RuntimeError("Open-Meteo devolvió una respuesta que no es JSON") from None


def pedir_openmeteo(finca):
    """Respuesta reciente (30 días + 7 de pronóstico) de una finca.

    ``forecast_days=8`` porque Open-Meteo cuenta el día de hoy en ese número:
    con 7 se recibirían solo 6 fechas ``> hoy`` y el contrato pide 7.
    """
    return _pedir_json(RECIENTE_URL, {
        "latitude": finca["lat"],
        "longitude": finca["lon"],
        "timezone": finca.get("zona_horaria") or ZONA_POR_DEFECTO,
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "hourly": "soil_moisture_0_to_7cm",
        "past_days": 45,
        "forecast_days": 8,
    })


def descargar_climatologia(finca, anio_ini=ANIO_INI, anio_fin=ANIO_FIN):
    """Normal mensual 1991–2020 de Open-Meteo archive (ERA5) para una finca.

    Una sola petición por finca (~11.000 días). Devuelve ``{"1991": {...}}``
    con `lluvia_mm` (total mensual) y `t2m` (media mensual).
    """
    respuesta = _pedir_json(ARCHIVO_URL, {
        "latitude": finca["lat"],
        "longitude": finca["lon"],
        "timezone": finca.get("zona_horaria") or ZONA_POR_DEFECTO,
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "start_date": f"{anio_ini}-01-01",
        "end_date": f"{anio_fin}-12-31",
    })
    return construir_climatologia(
        respuesta.get("daily") or {},
        anio_ini,
        anio_fin,
        incluir_temperatura=True,
    )


# --------------------------------------------------------------------------
# Archivos y caché
# --------------------------------------------------------------------------

def leer_fincas(ruta=FINCAS):
    """Lista de fincas de la tarea 1; ``None`` con un error claro si falta."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        print(f"No se pudo leer {ruta}: revisa que sea el JSON de la tarea 1.")
        return None
    fincas = (datos or {}).get("fincas") if isinstance(datos, dict) else None
    if not isinstance(fincas, list) or not fincas:
        print(f"{ruta} no tiene una lista «fincas» con datos.")
        return None
    return fincas


def cargar_climatologia(ruta, fincas, forzar=False):
    """Lee la climatología ERA5; si falta (o ``forzar``) la descarga."""
    if not forzar:
        try:
            with open(ruta, encoding="utf-8") as archivo:
                datos = json.load(archivo)
            if isinstance(datos, dict) and datos.get("fincas"):
                return datos
        except (OSError, ValueError):
            pass

    print(f"Descargando la normal 1991–{ANIO_FIN} de Open-Meteo archive (ERA5)...")
    entrada = {
        "version": 1,
        "fuente": "Open-Meteo archive (ERA5) · no NASA",
        "periodo": [ANIO_INI, ANIO_FIN],
        "nota": (
            "Normal de la misma fuente que el dato reciente (ERA5). "
            "lluvia_mm es total mensual; t2m es la media mensual de la "
            "temperatura media diaria (ampliación aditiva de la tarea 2)."
        ),
        "fincas": [],
    }
    fallos = 0
    for finca in fincas:
        nombre = finca.get("nombre") or finca.get("id")
        try:
            mensual = descargar_climatologia(finca)
        except Exception as error:
            fallos += 1
            print(f"  {nombre}: no se pudo descargar la normal ({error})")
            continue
        entrada["fincas"].append({"id": finca.get("id"), "mensual": mensual})
        print(f"  {nombre}: {len(mensual)} años")
    if fallos:
        print("Climatología incompleta: las fincas sin normal quedan con null.")
    if not entrada["fincas"]:
        return None
    escribir_atomico(ruta, entrada)
    return entrada


def _escribir_texto(ruta, texto):
    """Escribe texto con ``.tmp`` + ``os.replace``."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    temporal = f"{ruta}.tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        archivo.write(texto)
    os.replace(temporal, ruta)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def _recentrar(respuesta, finca, ahora):
    """Mueve las fechas de un fixture para que termine en ``hoy + 7`` (``--sin-red``).

    Los fixtures son respuestas reales recortadas y se quedan viejas. Desplazar
    sus fechas conserva los valores y permite ejercitar la ventana de 30 días y
    los 7 de pronóstico cualquier día, sin inventar datos meteorológicos. Se
    alinea el último día (hoy + 7), no el primero, para no quedarse sin futuro.
    """
    zona = ZoneInfo(finca.get("zona_horaria") or ZONA_POR_DEFECTO)
    hoy = ahora.astimezone(zona).date()
    diario = (respuesta or {}).get("daily") or {}
    tiempos = diario.get("time") or []
    if not tiempos:
        return respuesta
    try:
        ultima = dt.date.fromisoformat(str(tiempos[-1])[:10])
    except ValueError:
        return respuesta
    desplazamiento = (hoy + dt.timedelta(days=DIAS_PRONOSTICO)) - ultima
    if not desplazamiento.days:
        return respuesta

    for nombre in ("daily", "hourly"):
        bloque = respuesta.get(nombre) or {}
        nuevas = []
        for texto in bloque.get("time") or []:
            try:
                momento = dt.datetime.fromisoformat(str(texto))
            except ValueError:
                nuevas.append(texto)
                continue
            nuevas.append((momento + desplazamiento).isoformat(timespec="minutes"))
        if nuevas:
            bloque["time"] = nuevas
    return respuesta


def pedir_fixture(finca, ahora):
    """Respuesta del fixture de la finca, recentrada a hoy (sin red)."""
    nombre = FIXTURES_POR_FINCA.get(finca.get("id"))
    if not nombre:
        nombre = f"openmeteo_{finca.get('id')}.json"
    ruta = os.path.join(FIXTURES, nombre)
    try:
        with open(ruta, encoding="utf-8") as archivo:
            respuesta = json.load(archivo)
    except OSError:
        raise RuntimeError(f"falta el fixture {ruta}") from None
    return _recentrar(respuesta, finca, ahora)


def actualizar(fincas, pedir, ahora, ruta_json, ruta_js, climatologia):
    """Construye y escribe. ``pedir(finca)`` devuelve la respuesta de Open-Meteo o lanza.

    Si ``pedir`` lanza para todas las fincas: no reescribe nada y devuelve
    ``{"sin_conexion": True, "actualizado": <fecha del cache>}``.
    """
    respuestas = {}
    fallos = 0
    for finca in fincas:
        nombre = finca.get("nombre") or finca.get("id")
        try:
            respuestas[finca.get("id")] = pedir(finca)
        except Exception as error:
            fallos += 1
            print(f"  {nombre}: sin datos ({error})")

    if fincas and fallos == len(fincas):
        cache = leer_cache(ruta_json) or {}
        return {"sin_conexion": True, "actualizado": cache.get("actualizado")}

    objeto = construir_reciente(fincas, respuestas, climatologia, ahora)
    escribir_atomico(ruta_json, objeto)
    _escribir_texto(
        ruta_js,
        "window.__RECIENTE__ = "
        + json.dumps(objeto, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
    )
    return {
        "sin_conexion": False,
        "actualizado": objeto["actualizado"],
        "fincas": len(objeto["fincas"]),
        "avisos": list(objeto["avisos"]),
        "ventana": objeto["ventana"],
    }


def _ahora(fincas):
    zona = ZONA_POR_DEFECTO
    if fincas:
        zona = fincas[0].get("zona_horaria") or ZONA_POR_DEFECTO
    return dt.datetime.now(ZoneInfo(zona))


def main(argv=None):
    analizador = argparse.ArgumentParser(
        description="Actualiza el bloque «Esta temporada» desde Open-Meteo."
    )
    analizador.add_argument(
        "--sin-red",
        action="store_true",
        help="no llama a la red: usa los fixtures para ejercitar el pipeline.",
    )
    analizador.add_argument(
        "--recalcular-climatologia",
        action="store_true",
        help="vuelve a bajar la normal 1991–2020 y reescribe la climatología.",
    )
    analizador.add_argument("--fincas", default=FINCAS, help="JSON de fincas.")
    analizador.add_argument("--json", default=SALIDA_JSON, help="salida JSON.")
    analizador.add_argument("--js", default=SALIDA_JS, help="salida JS.")
    analizador.add_argument(
        "--climatologia", default=CLIMATOLOGIA, help="JSON de la normal ERA5."
    )
    argumentos = analizador.parse_args(argv)

    fincas = leer_fincas(argumentos.fincas)
    if fincas is None:
        print(
            "No existe datos/fincas.json (lo entrega la tarea 1). "
            "No se escribe nada.",
            file=sys.stderr,
        )
        return 2

    ahora = _ahora(fincas)
    climatologia = None
    if argumentos.sin_red:
        climatologia = None
        try:
            with open(argumentos.climatologia, encoding="utf-8") as archivo:
                climatologia = json.load(archivo)
        except (OSError, ValueError):
            print(
                "Sin climatología ERA5: las anomalías quedan con null. "
                "Corre sin --sin-red cuando haya red."
            )
    else:
        climatologia = cargar_climatologia(
            argumentos.climatologia, fincas, forzar=argumentos.recalcular_climatologia
        )
        if climatologia is None:
            print(
                "No se pudo generar la climatología ERA5: "
                "las anomalías quedan con null.",
                file=sys.stderr,
            )

    if argumentos.sin_red:
        pedir = lambda finca: pedir_fixture(finca, ahora)  # noqa: E731
    else:
        pedir = pedir_openmeteo

    print(f"Pidiendo el bloque reciente de {len(fincas)} finca(s)...")
    resultado = actualizar(
        fincas, pedir, ahora,
        argumentos.json, argumentos.js, climatologia,
    )

    if resultado.get("sin_conexion"):
        fecha = resultado.get("actualizado") or "una fecha desconocida"
        print(f"sin conexión: se mantiene el dato de {fecha}")
        return 1

    print(f"actualizado: {resultado['actualizado']}")
    print(f"fincas: {resultado['fincas']}")
    ventana = resultado.get("ventana") or {}
    print(f"ventana: {ventana.get('inicio')} → {ventana.get('fin')}")
    print(f"escrito: {argumentos.json} y {argumentos.js}")
    if resultado.get("avisos"):
        print(f"avisos ({len(resultado['avisos'])}):")
        for aviso in resultado["avisos"]:
            print(f"  - {aviso}")
    else:
        print("avisos: ninguno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
