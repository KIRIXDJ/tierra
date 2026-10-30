"""Prueba independiente de la API diaria de NASA POWER.

Consulta los últimos 365 días para tres sitios de República Dominicana y
resume la lluvia, los días secos, la temperatura media y la lluvia mensual.
La API de POWER no requiere clave y devuelve -999 en los días sin dato.

Uso:
    python prueba_power.py
"""

from __future__ import annotations

import datetime as dt
import sys

import requests

# La consola de Windows suele usar cp1252; la prueba imprime ° y flechas.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
COMUNIDAD = "AG"
PARAMETROS = (
    "PRECTOTCORR",        # lluvia corregida (mm/día)
    "T2M",                # temperatura media a 2 m (°C)
    "T2M_MAX",            # temperatura máxima a 2 m (°C)
    "T2M_MIN",            # temperatura mínima a 2 m (°C)
    "ALLSKY_SFC_SW_DWN",  # radiación solar de onda corta (MJ/m²/día)
    "RH2M",               # humedad relativa a 2 m (%)
    "GWETTOP",            # humedad superficial del suelo (0-1)
    "GWETROOT",           # humedad de la zona radicular (0-1)
    "GWETPROF",           # humedad del perfil del suelo (0-1)
)
DIAS = 365
FALTANTE = -999.0
UMBRAL_SECO = 1.0
TIMEOUT = (10, 60)

SITIOS = (
    ("Constanza", 18.91, -70.74),
    ("Azua", 18.45, -70.73),
    ("San Francisco de Macorís", 19.30, -70.25),
)
MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


class ErrorPower(Exception):
    """Fallo de red o de datos con un mensaje apto para consola."""


def _f(valor, defecto=None):
    """Convierte a float sin romper la lectura si el campo falta."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def periodo(dias=DIAS):
    """Últimos ``dias`` días cerrados, cortados al final del mes anterior.

    Si el rango toca el mes en curso, POWER mezcla la fuente GEOSIT y la
    lluvia diaria de toda la respuesta sale ~24 veces más alta (comprobado
    contra la API horaria). Por eso se pide hasta el último día del mes
    anterior, que siempre viene de MERRA2.
    """
    hoy = dt.date.today()
    hasta = hoy.replace(day=1) - dt.timedelta(days=1)
    desde = hasta - dt.timedelta(days=dias - 1)
    return desde, hasta


def consultar(lat, lon, desde, hasta, timeout=TIMEOUT):
    """Descarga las series diarias de POWER y las devuelve por parámetro.

    Devuelve ``(series, geometria, fuentes)``: las series como
    ``{parámetro: {YYYYMMDD: valor}}`` tal como las entrega la API (los días
    sin dato llegan con el relleno -999), la geometría del punto y las
    fuentes que usó POWER.
    """
    parametros = {
        "parameters": ",".join(PARAMETROS),
        "community": COMUNIDAD,
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    }

    try:
        respuesta = requests.get(
            POWER_URL,
            params=parametros,
            headers={"User-Agent": "tierra-power-prueba/1.0"},
            timeout=timeout,
        )
    except requests.Timeout:
        raise ErrorPower("Tiempo de espera agotado al consultar NASA POWER.") from None
    except requests.ConnectionError:
        raise ErrorPower("Sin conexión a Internet para consultar NASA POWER.") from None
    except requests.RequestException:
        raise ErrorPower("No se pudo consultar NASA POWER.") from None

    if respuesta.status_code == 429:
        raise ErrorPower("NASA POWER limitó las peticiones. Espera unos minutos.")
    if respuesta.status_code >= 500:
        raise ErrorPower("El servidor de NASA POWER no está disponible.")
    if respuesta.status_code >= 400:
        raise ErrorPower(
            f"NASA POWER rechazó la solicitud (HTTP {respuesta.status_code})."
        )

    try:
        datos = respuesta.json()
    except ValueError:
        raise ErrorPower("NASA POWER devolvió una respuesta inesperada.") from None

    if not isinstance(datos, dict):
        raise ErrorPower("NASA POWER devolvió una respuesta inesperada.")

    series = (datos.get("properties") or {}).get("parameter") or {}
    if not isinstance(series, dict) or not series:
        series = datos.get("parameters") or {}
    if not isinstance(series, dict):
        series = {}
    series = {
        nombre: valores for nombre, valores in series.items()
        if isinstance(valores, dict)
    }
    if not series:
        raise ErrorPower("NASA POWER no devolvió series diarias para ese punto.")

    return series, datos.get("geometry") or {}, datos.get("header") or {}


def _valor(serie, fecha):
    """Valor del día, o ``None`` si falta o viene con el relleno -999."""
    valor = _f((serie or {}).get(fecha))
    if valor is None or valor <= FALTANTE + 1.0:
        return None
    return valor


def resumir(series):
    """Calcula lluvia total, días secos, temperatura media y lluvia mensual."""
    fechas = sorted({
        fecha for valores in series.values() for fecha in valores
        if isinstance(fecha, str) and len(fecha) == 8 and fecha.isdigit()
    })
    if not fechas:
        raise ErrorPower("NASA POWER no devolvió fechas con datos.")

    lluvia = {fecha: _valor(series.get("PRECTOTCORR"), fecha) for fecha in fechas}
    temperatura = {fecha: _valor(series.get("T2M"), fecha) for fecha in fechas}

    validas = [valor for valor in lluvia.values() if valor is not None]
    dias_secos = sum(1 for valor in validas if valor < UMBRAL_SECO)
    racha = 0
    racha_max = 0
    for fecha in fechas:
        valor = lluvia[fecha]
        if valor is not None and valor < UMBRAL_SECO:
            racha += 1
            racha_max = max(racha_max, racha)
        else:
            racha = 0

    temps = [valor for valor in temperatura.values() if valor is not None]
    temp_media = sum(temps) / len(temps) if temps else None

    mensual = {}
    dias_mes = {}
    for fecha in fechas:
        valor = lluvia[fecha]
        if valor is None:
            continue
        mes = f"{fecha[:4]}-{fecha[4:6]}"
        mensual[mes] = mensual.get(mes, 0.0) + valor
        dias_mes[mes] = dias_mes.get(mes, 0) + 1

    return {
        "fechas": fechas,
        "lluvia_total_mm": round(sum(validas), 1) if validas else None,
        "dias_secos": dias_secos,
        "dias_con_dato": len(validas),
        "racha_seca_max": racha_max,
        "temp_media_c": round(temp_media, 1) if temp_media is not None else None,
        "mensual": [
            {"mes": mes, "mm": round(total, 1), "dias": dias_mes.get(mes, 0)}
            for mes, total in sorted(mensual.items())
        ],
    }


def imprimir(nombre, lat, lon, elevacion, resumen):
    """Muestra el resumen de un sitio con el formato de la prueba."""
    norte = "N" if lat >= 0 else "S"
    este = "E" if lon >= 0 else "O"
    altitud = f" · {elevacion:.0f} m" if elevacion is not None else ""
    print()
    print(f"--- {nombre} · {abs(lat):.2f}°{norte} {abs(lon):.2f}°{este}{altitud} ---")

    total = resumen["lluvia_total_mm"]
    print(f"  Lluvia total .......... {total if total is not None else 'sin dato'} mm")
    print(f"  Días secos (<1 mm) .... {resumen['dias_secos']} de {resumen['dias_con_dato']}")
    print(f"  Racha seca máxima ..... {resumen['racha_seca_max']} días")
    temp = resumen["temp_media_c"]
    print(f"  Temperatura media ..... {temp if temp is not None else 'sin dato'} °C")
    print("  Lluvia mensual:")
    for item in resumen["mensual"]:
        anio, mes = item["mes"].split("-")
        etiqueta = f"{MESES[int(mes) - 1]} {anio}"
        barra = "#" * max(1, int(round(item["mm"] / 20.0)))
        print(f"    {etiqueta:10s} {item['mm']:7.1f} mm  {item['dias']:2d} d  {barra}")


def main():
    desde, hasta = periodo()

    print("NASA POWER · API diaria por punto · comunidad AG")
    print(f"Periodo: {desde.isoformat()} → {hasta.isoformat()} ({DIAS} días)")
    print(f"Parámetros: {', '.join(PARAMETROS)}")

    fallos = 0
    for nombre, lat, lon in SITIOS:
        try:
            series, geometria, cabecera = consultar(lat, lon, desde, hasta)
            resumen = resumir(series)
        except ErrorPower as exc:
            fallos += 1
            print()
            print(f"--- {nombre} ---")
            print(f"  ERROR: {exc}")
            continue

        elevacion = None
        coordenadas = geometria.get("coordinates") or []
        if len(coordenadas) >= 3:
            elevacion = _f(coordenadas[2])
        imprimir(nombre, lat, lon, elevacion, resumen)
        if "GEOSIT" in (cabecera.get("sources") or []):
            print("  AVISO: POWER mezcló GEOSIT; la lluvia puede venir inflada.")

    print()
    if fallos == len(SITIOS):
        print("No se pudo completar ningún sitio. Revisa la conexión.")
        return 1
    if fallos:
        print(f"{fallos} de {len(SITIOS)} sitios fallaron.")
    else:
        print("Los tres sitios respondieron correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
