"""Cuenta incendios y tormentas de EONET por celda de 5 grados.

EONET no filtra por rango de fechas: ``days`` cuenta hacia atrás desde hoy.
Por eso se pide un año completo y se filtra por la fecha de la geometría.
"""

import datetime as dt
import time

import requests

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
CATEGORIAS = (
    ("wildfires", "incendios"),
    ("severeStorms", "tormentas"),
)
TIMEOUT = (10, 120)
PAUSA = 1.0


class ErrorEventos(Exception):
    """Fallo de red o de datos al consultar EONET."""


def celda_de(lat, lon, res=5):
    """Centro de la celda de ``res`` grados que contiene el punto."""
    lat = max(-90.0, min(90.0, float(lat)))
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    fila = round((lat + 90.0) / res - 0.5)
    columna = round((lon + 180.0) / res - 0.5)
    return (-90.0 + res * (fila + 0.5), -180.0 + res * (columna + 0.5))


def _punto(geometrias):
    """Latitud y longitud del evento: último Point o promedio del resto."""
    if not geometrias:
        return None
    ultima = geometrias[-1] or {}
    if ultima.get("type") == "Point":
        coordenadas = ultima.get("coordinates") or []
        if len(coordenadas) >= 2:
            return float(coordenadas[1]), float(coordenadas[0])

    puntos = []
    for geometria in geometrias:
        for par in (geometria or {}).get("coordinates") or []:
            if (isinstance(par, (list, tuple)) and len(par) >= 2
                    and isinstance(par[0], (int, float))):
                puntos.append((float(par[1]), float(par[0])))
            elif (isinstance(par, (list, tuple)) and par
                  and isinstance(par[0], (list, tuple))):
                for sub in par:
                    if isinstance(sub, (list, tuple)) and len(sub) >= 2:
                        puntos.append((float(sub[1]), float(sub[0])))
    if not puntos:
        return None
    return (
        sum(punto[0] for punto in puntos) / len(puntos),
        sum(punto[1] for punto in puntos) / len(puntos),
    )


def _anio(evento):
    geometrias = evento.get("geometry") or []
    if not geometrias:
        return None
    fecha = str((geometrias[-1] or {}).get("date", ""))
    try:
        return int(fecha[:4])
    except ValueError:
        return None


def descargar_eonet(categoria, desde, hasta, log=None):
    """Eventos de una categoría entre dos años, pedidos año a año."""
    eventos = []
    for anio in range(desde, hasta + 1):
        parametros = {
            "status": "all",
            "start": f"{anio}-01-01",
            "end": f"{anio}-12-31",
            "category": categoria,
        }
        for intento in range(2):
            try:
                respuesta = requests.get(EONET_URL, params=parametros, timeout=TIMEOUT)
                break
            except requests.Timeout:
                if intento:
                    raise ErrorEventos("Tiempo de espera agotado al consultar EONET.")
            except requests.RequestException:
                if intento:
                    raise ErrorEventos("No se pudo consultar EONET.")
            time.sleep(2.0)
        else:
            continue

        if respuesta.status_code >= 400:
            continue
        try:
            datos = respuesta.json()
        except ValueError:
            continue
        eventos.extend(
            evento for evento in datos.get("events", [])
            if _anio(evento) == anio
        )
        if log:
            log(anio, len(eventos))
        time.sleep(PAUSA)
    return eventos


def contar_eventos(desde=2016, hasta=2025, descargar=None, log=None):
    """Conteo por celda: ``{(lat, lon): {"incendios": n, "tormentas": m}}``."""
    if descargar is None:
        descargar = descargar_eonet

    conteo = {}
    for categoria, campo in CATEGORIAS:
        for evento in descargar(categoria, desde, hasta) or []:
            punto = _punto(evento.get("geometry") or [])
            if punto is None:
                continue
            celda = celda_de(*punto)
            registro = conteo.setdefault(celda, {"incendios": 0, "tormentas": 0})
            registro[campo] += 1
    return conteo
