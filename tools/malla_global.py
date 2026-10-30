"""Construye la malla global de tendencias con datos de NASA POWER.

Cada celda pide la serie anual 1984-2025 de cuatro variables y guarda la
pendiente de Sen por década, su p de Mann-Kendall y la media. El resultado se
inyecta en el HTML del demo con ``tools/html_malla.py``.
"""

import argparse
import concurrent.futures
import json
import math
import statistics
import sys
import threading
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.eventos import ErrorEventos, contar_eventos
from tools.html_malla import leer_malla, reemplazar_malla
from tools.power_cliente import ErrorPower, descargar_celda
from tools.tendencia import mann_kendall, pendiente_decada

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "web" / "index.html"
PARCIAL = Path(__file__).resolve().parent / ".malla_parcial.json"

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


_ritmo = threading.Lock()
_ultimo_envio = [0.0]


def _esperar_turno(intervalo=0.5):
    """Espacia las peticiones para no chocar con el límite de POWER."""
    with _ritmo:
        espera = _ultimo_envio[0] + intervalo - time.time()
        if espera > 0:
            time.sleep(espera)
        _ultimo_envio[0] = time.time()


def _reintentar(funcion, intentos=4, espera=20.0):
    """Repite una descarga ante fallos de red o límite de peticiones."""
    ultimo = None
    for intento in range(intentos):
        try:
            return funcion()
        except ErrorPower as error:
            ultimo = error
            time.sleep(espera * (intento + 1))
    raise ultimo


def _verificar():
    malla = leer_malla(HTML.read_text(encoding="utf-8"))
    celdas = malla.get("celdas", [])
    print(f"{len(celdas)} celdas · rejilla {malla.get('res')}°")
    for celda in celdas:
        if celda[0] == 17.5 and celda[1] == -72.5:
            pendiente = celda[2]
            texto = f"{pendiente:+.3f}" if pendiente is not None else "sin dato"
            print(f"RD 17.5/-72.5: T2M {texto} °C/década · p {celda[3]}")
            break


def main(argv=None):
    analizador = argparse.ArgumentParser(
        description="Genera la malla global de tendencias y la escribe en web/index.html"
    )
    analizador.add_argument("--rejilla", type=int, default=5)
    analizador.add_argument("--concurrencia", type=int, default=6)
    analizador.add_argument("--reanudar", action="store_true")
    analizador.add_argument("--verificar", action="store_true")
    analizador.add_argument("--sin-eventos", action="store_true")
    argumentos = analizador.parse_args(argv)

    if argumentos.verificar:
        _verificar()
        return 0

    if 180 % argumentos.rejilla or 360 % argumentos.rejilla:
        print("La rejilla debe dividir 180 y 360.")
        return 1

    parcial = {}
    if argumentos.reanudar and PARCIAL.exists():
        parcial = json.loads(PARCIAL.read_text(encoding="utf-8"))
        print(f"Reanudando con {len(parcial)} celdas ya descargadas.")

    candado = threading.Lock()

    def descargar_con_cache(lat, lon, variables, anio_ini, anio_fin):
        clave = f"{lat},{lon}"
        with candado:
            if clave in parcial:
                return parcial[clave]
        def una():
            _esperar_turno()
            try:
                return descargar_celda(lat, lon, variables, anio_ini, anio_fin)
            except ErrorPower as error:
                if "limitó" in str(error):
                    time.sleep(65)
                raise

        datos = _reintentar(una)
        with candado:
            parcial[clave] = datos
            if len(parcial) % 100 == 0:
                PARCIAL.write_text(
                    json.dumps(parcial, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                print(f"  punto de control: {len(parcial)} celdas")
        return datos

    conteos = {}
    if not argumentos.sin_eventos:
        print("Contando incendios y tormentas de EONET (2016-2025)...")
        try:
            conteos = contar_eventos(2016, 2025, log=lambda anio, n: print(
                f"  {anio}: {n} eventos acumulados"
            ))
            print(f"{len(conteos)} celdas con eventos.")
        except ErrorEventos as error:
            print(f"Aviso: sin capa de eventos ({error}).")

    total = len(centros(argumentos.rejilla))
    inicio = time.time()
    hechos = [0]

    def log(indice, lat, lon):
        hechos[0] += 1
        if hechos[0] % 50 == 0:
            transcurrido = max(0.1, time.time() - inicio)
            ritmo = hechos[0] / transcurrido
            restante = (total - hechos[0]) / max(ritmo, 1e-6)
            print(
                f"{hechos[0]}/{total} · {ritmo * 60:.0f} celdas/min"
                f" · ETA {restante / 60:.0f} min"
            )

    print(f"Descargando {total} celdas de {argumentos.rejilla}° con"
          f" concurrencia {argumentos.concurrencia}...")
    malla = construir_malla(
        res=argumentos.rejilla,
        descargar=descargar_con_cache,
        eventos=conteos,
        log=log,
        concurrencia=argumentos.concurrencia,
    )

    html = HTML.read_text(encoding="utf-8")
    HTML.write_text(reemplazar_malla(html, malla), encoding="utf-8")
    PARCIAL.unlink(missing_ok=True)
    print(f"{len(malla['celdas'])} celdas escritas en {HTML.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
