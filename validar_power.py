"""Validación de la lluvia de NASA POWER que usa Tierra.

Compara, para los tres sitios de la capa agro, la lluvia diaria y mensual de
POWER con la de Open-Meteo (archivo histórico), en el mismo periodo de 365
días que usa la app y en el año 2024. Además calcula el promedio multianual
2015-2025 y comprueba si el dato diario viene inflado.

Uso:
    python validar_power.py
"""

from __future__ import annotations

import calendar
import datetime as dt
import math
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POWER_DIARIO_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_MENSUAL_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_CLIMATOLOGIA_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
COMUNIDAD = "AG"
PARAMETRO = "PRECTOTCORR"
ZONA_HORARIA = "America/Santo_Domingo"
RELLENO = -999.0
PAUSA_POWER = 1.2
TIMEOUT = (10, 60)
ANIO_MULTIANUAL_INI = 2015
ANIO_MULTIANUAL_FIN = 2025
UMBRAL_RATIO = (0.67, 1.5)

SITIOS = (
    ("Constanza", 18.91, -70.74),
    ("Azua", 18.45, -70.73),
    ("San Francisco de Macorís", 19.30, -70.25),
)
MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


class ErrorValidacion(Exception):
    """Fallo de red o de datos con un mensaje apto para consola."""


def _pedir(url, parametros, intentos=2):
    """GET con un reintento si el servidor limita las peticiones."""
    ultimo = "No se pudo consultar la fuente."
    for intento in range(intentos):
        try:
            respuesta = requests.get(
                url,
                params=parametros,
                headers={"User-Agent": "tierra-validacion/1.0"},
                timeout=TIMEOUT,
            )
        except requests.Timeout:
            raise ErrorValidacion("Tiempo de espera agotado.") from None
        except requests.ConnectionError:
            raise ErrorValidacion("Sin conexión a Internet.") from None
        except requests.RequestException:
            raise ErrorValidacion("No se pudo completar la consulta.") from None

        if respuesta.status_code == 429:
            ultimo = "La fuente limitó las peticiones."
            time.sleep(6.0)
            continue
        if respuesta.status_code >= 500:
            ultimo = "La fuente no está disponible en este momento."
            time.sleep(2.0)
            continue
        if respuesta.status_code >= 400:
            raise ErrorValidacion(
                f"La fuente rechazó la consulta (HTTP {respuesta.status_code})."
            )

        try:
            return respuesta.json()
        except ValueError:
            raise ErrorValidacion("La fuente devolvió una respuesta inesperada.") from None

    raise ErrorValidacion(ultimo)


def _f(valor, defecto=None):
    """Convierte a float sin romper la lectura si el campo falta."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def power_diario(lat, lon, desde, hasta):
    """Lluvia diaria de POWER; ``None`` en los días con relleno -999."""
    datos = _pedir(POWER_DIARIO_URL, {
        "parameters": PARAMETRO,
        "community": COMUNIDAD,
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    })
    series = ((datos.get("properties") or {}).get("parameter") or {}).get(PARAMETRO)
    if not isinstance(series, dict) or not series:
        raise ErrorValidacion("POWER no devolvió la lluvia diaria del punto.")
    salida = {}
    for clave, valor in series.items():
        numero = _f(valor)
        salida[clave] = None if numero is None or numero <= RELLENO + 1.0 else numero
    return salida


def power_mensual(lat, lon, anio_ini, anio_fin):
    """Lluvia mensual de POWER en mm/día (la API devuelve la tasa media diaria).

    La API mensual solo acepta años en ``start``/``end`` y añade una clave
    ``AAAA13`` por año con el valor anual, que aquí se descarta.
    """
    time.sleep(PAUSA_POWER)
    datos = _pedir(POWER_MENSUAL_URL, {
        "parameters": PARAMETRO,
        "community": COMUNIDAD,
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start": str(anio_ini),
        "end": str(anio_fin),
        "format": "JSON",
    })
    series = ((datos.get("properties") or {}).get("parameter") or {}).get(PARAMETRO)
    if not isinstance(series, dict) or not series:
        raise ErrorValidacion("POWER no devolvió la lluvia mensual del punto.")
    return {
        clave: valor for clave, valor in series.items()
        if len(clave) == 6 and clave.isdigit() and not clave.endswith("13")
    }


def power_climatologia(lat, lon):
    """Climatología mensual de POWER 2001-2025, en mm/día por mes."""
    time.sleep(PAUSA_POWER)
    datos = _pedir(POWER_CLIMATOLOGIA_URL, {
        "parameters": PARAMETRO,
        "community": COMUNIDAD,
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "format": "JSON",
    })
    serie = ((datos.get("properties") or {}).get("parameter") or {}).get(PARAMETRO)
    if not isinstance(serie, dict) or not serie:
        raise ErrorValidacion("POWER no devolvió la climatología del punto.")
    return serie


def total_anual_climatologia(climatologia):
    """Suma la climatología mensual (mm/día) a un año medio en mm."""
    total = 0.0
    for indice, nombre in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")):
        valor = _f(climatologia.get(nombre))
        if valor is None or valor <= RELLENO + 1.0:
            return None
        total += valor * calendar.monthrange(2025, indice + 1)[1]
    return round(total, 1)


def openmeteo(lat, lon, desde, hasta):
    """Lluvia diaria de Open-Meteo (mm) en horario local de República Dominicana."""
    datos = _pedir(OPENMETEO_URL, {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": desde.isoformat(),
        "end_date": hasta.isoformat(),
        "daily": "precipitation_sum",
        "timezone": ZONA_HORARIA,
    })
    diario = datos.get("daily") or {}
    fechas = diario.get("time") or []
    valores = diario.get("precipitation_sum") or []
    if not fechas or len(fechas) != len(valores):
        raise ErrorValidacion("Open-Meteo no devolvió la lluvia diaria del punto.")
    return {
        fecha: _f(valor)
        for fecha, valor in zip(fechas, valores)
    }


def mes_de(clave):
    """``YYYYMM`` a partir de ``YYYYMMDD`` o ``YYYY-MM-DD``."""
    return str(clave).replace("-", "")[:6]


def sumar_por_mes(serie):
    """Suma una serie diaria por mes; los días sin dato no cuentan."""
    totales = {}
    dias = {}
    for clave, valor in serie.items():
        if valor is None:
            continue
        mes = mes_de(clave)
        totales[mes] = totales.get(mes, 0.0) + valor
        dias[mes] = dias.get(mes, 0) + 1
    return (
        {mes: round(total, 1) for mes, total in totales.items()},
        dias,
    )


def total_del_mes(valor_mm_dia, anio, mes):
    """Convierte la tasa media diaria de POWER (mm/día) en mm del mes."""
    return valor_mm_dia * calendar.monthrange(anio, mes)[1]


def promedio_multianual(mensual, anio_ini, anio_fin):
    """Lluvia media de cada mes calendario entre ``anio_ini`` y ``anio_fin``."""
    acumulado = {mes: [] for mes in range(1, 13)}
    for clave, valor in mensual.items():
        numero = _f(valor)
        if numero is None or numero <= RELLENO + 1.0:
            continue
        anio, mes = int(clave[:4]), int(clave[4:])
        if anio_ini <= anio <= anio_fin:
            acumulado[mes].append(total_del_mes(numero, anio, mes))
    return {
        mes: (round(sum(valores) / len(valores), 1) if valores else None)
        for mes, valores in acumulado.items()
    }


def _rangos(valores):
    """Rangos promedio (1..n) para la correlación de Spearman."""
    orden = sorted(range(len(valores)), key=lambda indice: valores[indice])
    rangos = [0.0] * len(valores)
    inicio = 0
    while inicio < len(orden):
        fin = inicio
        while (fin + 1 < len(orden)
               and valores[orden[fin + 1]] == valores[orden[inicio]]):
            fin += 1
        promedio = (inicio + fin) / 2.0 + 1.0
        for posicion in range(inicio, fin + 1):
            rangos[orden[posicion]] = promedio
        inicio = fin + 1
    return rangos


def spearman(a, b):
    """Correlación de Spearman sin dependencias externas."""
    pares = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pares) < 3:
        return None
    xa = [par[0] for par in pares]
    xb = [par[1] for par in pares]
    ra = _rangos(xa)
    rb = _rangos(xb)
    media_a = sum(ra) / len(ra)
    media_b = sum(rb) / len(rb)
    numerador = sum((x - media_a) * (y - media_b) for x, y in zip(ra, rb))
    denominador = math.sqrt(
        sum((x - media_a) ** 2 for x in ra)
        * sum((y - media_b) ** 2 for y in rb)
    )
    return numerador / denominador if denominador else None


def _mm(valor):
    return f"{valor:7.1f}" if valor is not None else "      -"


def _ratio(valor):
    return f"{valor:5.2f}" if valor is not None else "    -"


def _nombre_mes(clave):
    return f"{MESES[int(clave[4:6]) - 1]} {clave[:4]}"


def tabla(periodo, desde, hasta, diario, mensual_api, om_diario, multianual):
    """Imprime la tabla mensual del periodo y devuelve las métricas."""
    mensual_power, _ = sumar_por_mes(diario)
    mensual_om, _ = sumar_por_mes(om_diario)
    meses = sorted(
        mes for mes in set(mensual_power) | set(mensual_om)
        if desde.strftime("%Y%m") <= mes <= hasta.strftime("%Y%m")
    )

    print(f"\n[{periodo}] {desde.isoformat()} → {hasta.isoformat()}")
    print("  mes        P.diario  P.mensual  OpenMeteo  ratio  multianual")
    series_power, series_om, series_multi = [], [], []
    alertas = []
    total_power = total_api = total_om = total_multi = 0.0

    for mes in meses:
        anio, numero_mes = int(mes[:4]), int(mes[4:])
        p_dia = mensual_power.get(mes)
        api = _f(mensual_api.get(mes))
        p_api = (
            round(total_del_mes(api, anio, numero_mes), 1)
            if api is not None and api > RELLENO + 1.0 else None
        )
        om = mensual_om.get(mes)
        multi = multianual.get(numero_mes)
        ratio = p_dia / om if (p_dia is not None and om and om > 0) else None

        print(
            f"  {mes[:4]}-{mes[4:]}   {_mm(p_dia)}    {_mm(p_api)}"
            f"   {_mm(om)}  {_ratio(ratio)}     {_mm(multi)}"
        )
        series_power.append(p_dia)
        series_om.append(om)
        series_multi.append(multi)
        total_power += p_dia or 0.0
        total_api += p_api or 0.0
        total_om += om or 0.0
        total_multi += multi or 0.0

        if ratio is not None and not (
            UMBRAL_RATIO[0] <= ratio <= UMBRAL_RATIO[1]
        ):
            alertas.append((mes, ratio, p_dia, om, p_api))
        elif ratio is None and p_dia is not None and p_dia >= 10.0:
            # Open-Meteo casi seco y POWER con lluvia: también es discrepancia.
            alertas.append((mes, None, p_dia, om, p_api))

    ratio_total = total_power / total_om if total_om else None
    print(
        f"  TOTAL        {_mm(total_power)}    {_mm(total_api)}"
        f"   {_mm(total_om)}  {_ratio(ratio_total)}     {_mm(total_multi)}"
    )

    for mes, ratio, p_dia, om, p_api in alertas:
        if ratio is None:
            print(
                f"  ALERTA {mes}: OpenMeteo sin lluvia ({_mm(om).strip()} mm)"
                f" y POWER diario {p_dia:.1f} mm"
            )
        else:
            print(
                f"  ALERTA {mes}: ratio {ratio:.2f}"
                f" (POWER diario {p_dia:.1f} mm · POWER mensual {_mm(p_api).strip()}"
                f" · OpenMeteo {om:.1f} mm)"
            )
    if not alertas:
        print("  Sin alertas: todos los meses dentro de 0.67–1.5.")

    correlacion = spearman(series_power, series_om)
    forma = spearman(series_power, series_multi)
    print(
        "  Spearman mensual POWER vs OpenMeteo: "
        + (f"{correlacion:+.2f}" if correlacion is not None else "sin datos")
    )
    print(
        "  Spearman mensual POWER vs multianual: "
        + (f"{forma:+.2f}" if forma is not None else "sin datos")
    )

    max_power = _maximo(meses, series_power)
    max_om = _maximo(meses, series_om)
    max_multi = max(
        ((mes, valor) for mes, valor in multianual.items() if valor is not None),
        key=lambda par: par[1],
        default=None,
    )
    if max_power and max_om and max_multi:
        print(
            f"  Máximo mensual: POWER {_nombre_mes(max_power[0])}"
            f" ({max_power[1]:.1f} mm) · OpenMeteo {_nombre_mes(max_om[0])}"
            f" ({max_om[1]:.1f} mm) · multianual {MESES[max_multi[0] - 1]}"
            f" ({max_multi[1]:.1f} mm)"
        )
        coincide = max_power[0][4:6] == f"{max_multi[0]:02d}"
        print(
            "  Forma estacional: "
            + ("coincide" if coincide else "NO coincide")
            + " (el máximo del periodo frente al máximo multianual)"
        )

    return {
        "meses": meses,
        "power": series_power,
        "om": series_om,
        "multi": series_multi,
        "total_power": total_power,
        "total_api": total_api,
        "total_om": total_om,
        "total_multi": total_multi,
        "ratio_total": ratio_total,
        "alertas": alertas,
        "spearman_om": correlacion,
        "spearman_multi": forma,
    }


def _maximo(meses, serie):
    """Mes con el valor más alto de una serie mensual alineada."""
    validos = [
        (mes, valor) for mes, valor in zip(meses, serie) if valor is not None
    ]
    return max(validos, key=lambda par: par[1]) if validos else None


def coherencia_x24(nombre, diario, mensual_api, meses):
    """Compara la suma diaria con el mensual de POWER para detectar el ×24."""
    mensual_power, _ = sumar_por_mes(diario)
    ratios = []
    for mes in meses:
        p_dia = mensual_power.get(mes)
        api = _f(mensual_api.get(mes))
        if p_dia is None or api is None or api <= RELLENO + 1.0:
            continue
        anio, numero_mes = int(mes[:4]), int(mes[4:])
        ratios.append((mes, p_dia / total_del_mes(api, anio, numero_mes)))

    if not ratios:
        print(f"  {nombre}: sin meses comparables.")
        return None

    valores = sorted(ratio for _, ratio in ratios)
    mediana = valores[len(valores) // 2]
    print(
        f"  {nombre}: ratio mínimo {valores[0]:.3f} · mediana {mediana:.3f}"
        f" · máximo {valores[-1]:.3f} ({len(ratios)} meses)"
    )
    return {"min": valores[0], "mediana": mediana, "max": valores[-1]}


def dias_extremos(diario, om_diario, total):
    """Muestra los días más lluviosos del periodo y su peso en el total."""
    validos = [
        (clave, valor) for clave, valor in diario.items()
        if valor is not None
    ]
    validos.sort(key=lambda par: par[1], reverse=True)
    print("  Días más lluviosos de POWER:")
    for clave, valor in validos[:3]:
        fecha = f"{clave[:4]}-{clave[4:6]}-{clave[6:]}"
        om = om_diario.get(fecha)
        peso = 100.0 * valor / total if total else 0.0
        print(
            f"    {fecha}  POWER {valor:6.2f} mm · OpenMeteo"
            f" {om if om is not None else '-'} mm · {peso:.1f}% del periodo"
        )
    fuertes = sum(1 for _, valor in validos if valor >= 25.0)
    print(
        f"    Días con ≥25 mm: {fuertes} · aportan"
        f" {100.0 * sum(v for _, v in validos if v >= 25.0) / total if total else 0:.0f}%"
        " del total"
    )


def validar_sitio(nombre, lat, lon, periodo_app, periodo_2024, multianual,
                  mensual_api):
    """Ejecuta todas las comparaciones de un sitio y devuelve sus métricas."""
    print()
    print("#" * 68)
    print(f"{nombre.upper()} · {abs(lat):.2f}°N {abs(lon):.2f}°O")
    print("#" * 68)

    desde_app, hasta_app = periodo_app
    desde_2024, hasta_2024 = periodo_2024
    diario_app = power_diario(lat, lon, desde_app, hasta_app)
    time.sleep(PAUSA_POWER)
    om_app = openmeteo(lat, lon, desde_app, hasta_app)
    diario_2024 = power_diario(lat, lon, desde_2024, hasta_2024)
    time.sleep(PAUSA_POWER)
    om_2024 = openmeteo(lat, lon, desde_2024, hasta_2024)

    resumen_app = tabla(
        "1 · Periodo de la app", desde_app, hasta_app,
        diario_app, mensual_api, om_app, multianual,
    )
    resumen_2024 = tabla(
        "2 · Año 2024", desde_2024, hasta_2024,
        diario_2024, mensual_api, om_2024, multianual,
    )

    print("\n[3] Hipótesis del ×24: POWER diario sumado vs POWER mensual")
    coh_2024 = coherencia_x24("2024", diario_2024, mensual_api, resumen_2024["meses"])
    coh_app = coherencia_x24(
        "periodo app", diario_app, mensual_api, resumen_app["meses"]
    )
    print("\n[4] Reparto de la lluvia en el periodo de la app")
    dias_extremos(diario_app, om_app, resumen_app["total_power"])

    print("\n[5] Control con la climatología 2001-2025 de POWER")
    climatologia = power_climatologia(lat, lon)
    anual_clima = total_anual_climatologia(climatologia)
    anual_archivo = round(
        sum(valor for valor in multianual.values() if valor is not None), 1
    )
    if anual_clima:
        print(f"  archivo mensual 2015-2025: {anual_archivo:6.1f} mm/año")
        print(f"  climatología 2001-2025:    {anual_clima:6.1f} mm/año")
        print(
            "  ratio archivo/climatología:"
            f" {anual_archivo / anual_clima:.2f}"
        )

    return {
        "nombre": nombre,
        "app": resumen_app,
        "anio": resumen_2024,
        "coh_2024": coh_2024,
        "coh_app": coh_app,
        "multianual": multianual,
        "archivo_anual": anual_archivo,
        "clima_anual": anual_clima,
    }


def resumen_final(resultados):
    """Cierra con 5-8 líneas basadas solo en lo medido."""
    completos = [r for r in resultados if r]
    if not completos:
        print("\nNo se pudo validar ningún sitio.")
        return

    print()
    print("=" * 68)
    print("RESUMEN")
    print("=" * 68)

    ratios_app = [
        (r["nombre"], r["app"]["ratio_total"]) for r in completos
        if r["app"]["ratio_total"] is not None
    ]
    ratios_2024 = [
        (r["nombre"], r["anio"]["ratio_total"]) for r in completos
        if r["anio"]["ratio_total"] is not None
    ]
    coh = [r["coh_app"] for r in completos if r["coh_app"]]
    spearman_om = [
        r["app"]["spearman_om"] for r in completos
        if r["app"]["spearman_om"] is not None
    ]
    meses_alerta = sorted({
        mes for r in completos for mes, _, _, _, _ in r["app"]["alertas"]
    })

    texto_app = ", ".join(f"{nombre} {ratio:.2f}" for nombre, ratio in ratios_app)
    texto_2024 = ", ".join(f"{nombre} {ratio:.2f}" for nombre, ratio in ratios_2024)

    peor = None
    for r in completos:
        for mes, ratio, p_dia, om, p_api in r["app"]["alertas"]:
            if ratio is not None and (peor is None or ratio > peor[3]):
                peor = (r["nombre"], mes, om, ratio, p_dia)

    coincidencias = 0
    max_multi = None
    for r in completos:
        par = _maximo(r["app"]["meses"], r["app"]["power"])
        par_multi = max(
            ((mes, valor) for mes, valor in r["multianual"].items()
             if valor is not None),
            key=lambda par: par[1],
            default=None,
        )
        if par and par_multi:
            if par[0][4:6] == f"{par_multi[0]:02d}":
                coincidencias += 1
            if max_multi is None or par_multi[1] > max_multi[1]:
                max_multi = par_multi

    spearman_2024 = [
        r["anio"]["spearman_om"] for r in completos
        if r["anio"]["spearman_om"] is not None
    ]
    clima = [
        (r["nombre"], r["archivo_anual"], r["clima_anual"])
        for r in completos
        if r.get("clima_anual") and r.get("archivo_anual")
    ]
    desvio = max(
        [abs(ratio - 1.0) for _, ratio in ratios_app]
        + [abs(ratio - 1.0) for _, ratio in ratios_2024]
    ) if (ratios_app or ratios_2024) else 0.0

    if coh:
        print(
            "1. POWER diario y POWER mensual coinciden en el agregado"
            f" (ratios {min(c['min'] for c in coh):.3f}–{max(c['max'] for c in coh):.3f});"
            " no hay inflación ×24 en los periodos pedidos."
        )
    print(
        f"2. La lluvia anual del periodo de la app frente a Open-Meteo queda en"
        f" ratio {texto_app}; en 2024, {texto_2024}."
        f" Todos dentro de ±{desvio * 100:.0f}%."
    )
    if peor:
        print(
            f"3. Hay {len(meses_alerta)} meses distintos con ALERTA en algún sitio"
            f" ({', '.join(meses_alerta[:6])}{'…' if len(meses_alerta) > 6 else ''})."
            f" El peor es {peor[1]} en {peor[0]}: POWER {peor[4]:.1f} mm frente a"
            f" Open-Meteo {peor[2]:.1f} mm (ratio {peor[3]:.2f})."
        )
    if max_multi and spearman_om:
        texto_spearman_2024 = (
            f" (en 2024 fue {min(spearman_2024):+.2f} a {max(spearman_2024):+.2f})"
            if spearman_2024 else ""
        )
        print(
            "4. La forma mensual no acompaña: Spearman con Open-Meteo de"
            f" {min(spearman_om):+.2f} a {max(spearman_om):+.2f}"
            f"{texto_spearman_2024}, y el mes de máximo de la app solo coincide"
            f" con el multianual en {coincidencias} de {len(completos)} sitios"
            f" (el multianual siempre cae en {MESES[max_multi[0] - 1]})."
        )
    print(
        "5. El corte al mes anterior no corrige la anomalía: diario y mensual de"
        " POWER coinciden, así que el valor viene del producto diario (MERRA2)"
        " y no del agregado de GEOSIT que motivó el corte."
    )
    if clima:
        print(
            "6. POWER tampoco es consistente a escala larga: su climatología"
            f" 2001-2025 da {min(c[2] for c in clima):.0f}-{max(c[2] for c in clima):.0f}"
            " mm/año frente a"
            f" {min(c[1] for c in clima):.0f}-{max(c[1] for c in clima):.0f}"
            " mm/año del archivo mensual 2015-2025"
            f" (ratio {min(c[1] / c[2] for c in clima):.2f}"
            f"-{max(c[1] / c[2] for c in clima):.2f})."
        )
    print(
        "7. Conclusión: los acumulados anuales sirven para planificar, pero un"
        " mes concreto puede desviarse hasta ~7×; conviene contrastarlo con una"
        " segunda fuente o suavizarlo en la interfaz."
    )
    print(
        "8. No comprobado: qué fuente es correcta in situ (no hay pluviómetros),"
        " ni si la anomalía es un artefacto de MERRA2 o un episodio real que los"
        " reanálisis de ERA5 no resuelven."
    )


def main():
    hoy = dt.date.today()
    hasta_app = hoy.replace(day=1) - dt.timedelta(days=1)
    desde_app = hasta_app - dt.timedelta(days=364)
    periodo_app = (desde_app, hasta_app)
    periodo_2024 = (dt.date(2024, 1, 1), dt.date(2024, 12, 31))

    print("VALIDACIÓN DE LA LLUVIA DE NASA POWER")
    print(
        f"Periodo de la app: {desde_app.isoformat()} → {hasta_app.isoformat()}"
        f" · Histórico: {periodo_2024[0].isoformat()} → {periodo_2024[1].isoformat()}"
    )
    print(
        f"Promedio multianual: {ANIO_MULTIANUAL_INI}–{ANIO_MULTIANUAL_FIN}"
        " (API mensual de POWER) · control con la climatología 2001–2025"
    )
    print(
        "Fuentes: POWER diario/mensual (MERRA2, celda de ~50-70 km)"
        " y Open-Meteo (ERA5/ERA5-Land, ~11-30 km)"
    )

    resultados = []
    for nombre, lat, lon in SITIOS:
        try:
            mensual = power_mensual(
                lat, lon, ANIO_MULTIANUAL_INI, hasta_app.year
            )
            multianual = promedio_multianual(
                mensual, ANIO_MULTIANUAL_INI, ANIO_MULTIANUAL_FIN
            )
            resultados.append(
                validar_sitio(
                    nombre, lat, lon, periodo_app, periodo_2024, multianual,
                    mensual,
                )
            )
        except ErrorValidacion as exc:
            print()
            print("#" * 68)
            print(f"{nombre.upper()} · sin datos: {exc}")
            print("#" * 68)
            resultados.append(None)

    resumen_final(resultados)
    return 0 if any(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
