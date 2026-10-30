"""Cliente mínimo de NASA POWER: serie mensual de un punto.

La API mensual solo acepta años en ``start``/``end`` y devuelve los valores
en la unidad del parámetro (mm/día para la lluvia). Aquí solo se piden las
claves anuales ``AAAA13``, que ya vienen calculadas.
"""

import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
COMUNIDAD = "AG"
RELLENO = -999.0


class ErrorPower(Exception):
    """Fallo de red o de datos con un mensaje apto para consola."""


def _f(valor, defecto=None):
    """Convierte a float sin romper la lectura si el campo falta."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def descargar_celda(lat, lon, variables, anio_ini=1984, anio_fin=2025):
    """Serie anual de cada variable para el punto, con ``None`` donde falte."""
    parametros = {
        "parameters": ",".join(variables),
        "community": COMUNIDAD,
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start": str(anio_ini),
        "end": str(anio_fin),
        "format": "JSON",
    }

    try:
        respuesta = requests.get(POWER_URL, params=parametros, timeout=(10, 90))
    except requests.Timeout:
        raise ErrorPower("Tiempo de espera agotado al consultar NASA POWER.") from None
    except requests.RequestException:
        raise ErrorPower("No se pudo consultar NASA POWER.") from None

    if respuesta.status_code == 429:
        raise ErrorPower("NASA POWER limitó las peticiones. Espera un momento.")
    if respuesta.status_code >= 500:
        raise ErrorPower("El servidor de NASA POWER no está disponible.")
    if respuesta.status_code >= 400:
        raise ErrorPower("NASA POWER rechazó la solicitud.")

    try:
        datos = respuesta.json()
    except ValueError:
        raise ErrorPower("NASA POWER devolvió una respuesta inesperada.") from None

    series = (datos.get("properties") or {}).get("parameter") or {}
    salida = {}
    for variable in variables:
        valores = series.get(variable) or {}
        serie = []
        for anio in range(anio_ini, anio_fin + 1):
            numero = _f(valores.get(f"{anio}13"))
            if numero is None or numero <= RELLENO + 1.0:
                serie.append(None)
            else:
                serie.append(numero)
        salida[variable] = serie
    return salida
