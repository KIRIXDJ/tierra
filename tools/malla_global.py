"""Construye la malla global de tendencias con datos de NASA POWER.

Cada celda pide la serie anual 1984-2025 de cuatro variables y guarda la
pendiente de Sen por década, su p de Mann-Kendall y la media. El resultado se
inyecta en el HTML del demo con ``tools/html_malla.py``.
"""

import concurrent.futures
import math
import statistics

from tools.power_cliente import descargar_celda
from tools.tendencia import mann_kendall, pendiente_decada

ANIO_INI = 1984
ANIO_FIN = 2025
MIN_ANIOS = 30

VARIABLES = (
    {"id": "T2M", "nombre": "Temperatura", "unidad": "°C/década", "factor": 1.0},
    {"id": "PRECTOTCORR", "nombre": "Lluvia",
     "unidad": "mm/año por década", "factor": 365.25},
    {"id": "WS2M", "nombre": "Viento", "unidad": "m/s por década", "factor": 1.0},
    {"id": "RH2M", "nombre": "Humedad", "unidad": "%/década", "factor": 1.0},
)


def centros(res):
    """Centros de las celdas de ``res`` grados, de sur a norte y de oeste a este."""
    n_lat = 180 // res
    n_lon = 360 // res
    return [
        (-90.0 + res * (i + 0.5), -180.0 + res * (j + 0.5))
        for i in range(n_lat)
        for j in range(n_lon)
    ]


def _percentil(valores, cuantil):
    """Percentil con interpolación lineal (mismo criterio que numpy)."""
    datos = sorted(valores)
    if not datos:
        return None
    posicion = (len(datos) - 1) * cuantil
    bajo = math.floor(posicion)
    alto = math.ceil(posicion)
    if bajo == alto:
        return datos[int(posicion)]
    return datos[bajo] * (alto - posicion) + datos[alto] * (posicion - bajo)


def _campos(lat, lon, variables, series, eventos):
    """Los 16 campos de una celda: coordenadas, variables y conteos."""
    campos = [lat, lon]
    for variable in variables:
        serie = series.get(variable["id"]) or []
        validos = [valor for valor in serie if valor is not None]
        if len(validos) < MIN_ANIOS:
            campos.extend([None, None, None])
            continue
        factor = variable["factor"]
        ajustada = [valor * factor for valor in validos]
        prueba = mann_kendall(ajustada)
        campos.append(
            None if pendiente_decada(ajustada) is None
            else round(pendiente_decada(ajustada), 4)
        )
        campos.append(None if prueba is None else round(prueba[1], 6))
        campos.append(round(statistics.fmean(ajustada), 2))

    conteo = (eventos or {}).get((lat, lon), {})
    campos.append(int(conteo.get("incendios", 0)))
    campos.append(int(conteo.get("tormentas", 0)))
    return campos


def _dominios(variables, celdas):
    """Dominio simétrico por variable a partir de los percentiles 5 y 95."""
    dominios = []
    for indice, _ in enumerate(variables):
        posicion = 2 + indice * 3
        pendientes = [
            celda[posicion] for celda in celdas if celda[posicion] is not None
        ]
        if not pendientes:
            dominios.append(1.0)
            continue
        extremo = max(abs(_percentil(pendientes, 0.05)),
                      abs(_percentil(pendientes, 0.95)))
        dominios.append(round(extremo, 3) if extremo > 1e-9 else 1.0)
    return dominios


def construir_malla(res=5, variables=VARIABLES, descargar=descargar_celda,
                    eventos=None, log=None, concurrencia=1):
    """Descarga todas las celdas y devuelve el diccionario de la malla."""
    puntos = centros(res)
    ids = [variable["id"] for variable in variables]
    celdas = [None] * len(puntos)

    def trabajo(indice):
        lat, lon = puntos[indice]
        series = descargar(lat, lon, ids, ANIO_INI, ANIO_FIN)
        if log:
            log(indice, lat, lon)
        return indice, _campos(lat, lon, variables, series, eventos)

    if concurrencia > 1:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrencia
        ) as ejecutor:
            for indice, campos in ejecutor.map(trabajo, range(len(puntos))):
                celdas[indice] = campos
    else:
        for indice in range(len(puntos)):
            _, campos = trabajo(indice)
            celdas[indice] = campos

    dominios = _dominios(variables, celdas)
    return {
        "version": 1,
        "res": res,
        "anio_ini": ANIO_INI,
        "anio_fin": ANIO_FIN,
        "variables": [
            {
                "id": variable["id"],
                "nombre": variable["nombre"],
                "unidad": variable["unidad"],
                "dominio": dominios[indice],
            }
            for indice, variable in enumerate(variables)
        ],
        "celdas": celdas,
    }
