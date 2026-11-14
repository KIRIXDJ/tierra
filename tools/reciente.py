"""Seguimiento de la temporada con Open-Meteo: lógica pura, sin red ni I/O.

Este módulo arma el bloque "Esta temporada" de `datos/reciente.json`
(contrato en `interno/tareas/00-contratos.md`). No pide datos ni escribe archivos:
`actualizar_reciente.py` se encarga de la red y de los archivos.

Reglas que este código no puede romper:

- La anomalía compara **la misma fuente**: reciente de Open-Meteo contra la
  normal de Open-Meteo/ERA5 (`datos/climatologia_era5.json`). POWER no entra.
- Falta un dato → ``None`` y una frase en ``avisos``; nunca ``0``.
- La ventana son 30 días completos, ``fin = ayer`` en la zona de la finca.
- ``soil_moisture_0_to_7cm`` es la capa **superficial 0–7 cm**, no la raíz.

Nota de contrato (ampliación aditiva): para la anomalía de temperatura hace
falta una normal de temperatura de ERA5, y el contrato de
`datos/climatologia_era5.json` solo guardaba `lluvia_mm`. Se añade `t2m`
(media mensual de la temperatura media diaria, misma petición y misma fuente)
sin quitar ni cambiar `lluvia_mm`. Si el grupo prefiere no ampliarlo, la
temperatura queda con `null` y su aviso, que es el comportamiento por defecto
cuando no hay climatología.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

VERSION = 1
DIAS_VENTANA = 30
DIAS_PRONOSTICO = 7
DIAS_HUMEDAD = 7

NOTA_HUMEDAD = "capa 0–7 cm; sin climatología comparable"
UNIDAD_HUMEDAD = "m³/m³"
UNIDADES_HUMEDAD = ("m³/m³", "m3/m3", "m³/m3", "m3/m³")


# --------------------------------------------------------------------------
# Utilidades internas
# --------------------------------------------------------------------------

def _red(valor, decimales=1):
    """Redondea sin romper con ``None``."""
    if valor is None:
        return None
    return round(float(valor), decimales)


def _media(valores):
    """Media de los valores válidos; ``None`` si no hay ninguno."""
    validos = [v for v in valores if v is not None]
    if not validos:
        return None
    return sum(validos) / len(validos)


def _dias_mes(anio, mes):
    return calendar.monthrange(anio, mes)[1]


def _fracciones_ventana(inicio, fin):
    """Días de cada mes dentro de la ventana: ``{mes: días}``."""
    dias = {}
    fecha = inicio
    while fecha <= fin:
        dias[fecha.month] = dias.get(fecha.month, 0) + 1
        fecha += dt.timedelta(days=1)
    return dias


def _zona(finca_o_zona):
    """Acepta un id de zona o un diccionario de finca."""
    if isinstance(finca_o_zona, dict):
        zona = finca_o_zona.get("zona_horaria") or "America/Santo_Domingo"
    else:
        zona = finca_o_zona or "America/Santo_Domingo"
    return ZoneInfo(zona)


def _ahora_consciente(ahora):
    """Si llega una fecha sin zona, se asume UTC (nunca la de la máquina)."""
    if ahora.tzinfo is None:
        return ahora.replace(tzinfo=dt.timezone.utc)
    return ahora


def _fecha_local(ahora, zona):
    return _ahora_consciente(ahora).astimezone(zona).date()


def _fecha_de(valor):
    """Convierte ``date``, ``datetime`` o texto ISO a ``date`` (o ``None``)."""
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    try:
        return dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(str(valor)[:10])
        except ValueError:
            return None


# --------------------------------------------------------------------------
# Funciones del contrato
# --------------------------------------------------------------------------

def percentil(valores, q):
    """Percentil ``q`` (0..1) con interpolación lineal; ``None`` sin datos."""
    if q is None:
        return None
    validos = sorted(float(v) for v in valores if v is not None)
    if not validos:
        return None
    if q <= 0:
        return float(validos[0])
    if q >= 1:
        return float(validos[-1])
    posicion = (len(validos) - 1) * float(q)
    bajo = math.floor(posicion)
    alto = math.ceil(posicion)
    if bajo == alto:
        return float(validos[bajo])
    peso = posicion - bajo
    return float(validos[bajo] * (1.0 - peso) + validos[alto] * peso)


def ventana(fin, dias=DIAS_VENTANA):
    """``(inicio, fin)`` de ``dias`` días completos que terminan en ``fin``."""
    return fin - dt.timedelta(days=dias - 1), fin


def construir_climatologia(diario, anio_ini, anio_fin, incluir_temperatura=False):
    """Totales mensuales de lluvia (mm) desde el diario de Open-Meteo.

    Devuelve ``{"1991": {"lluvia_mm": [12 valores]}, ...}``. Con
    ``incluir_temperatura=True`` añade ``t2m``: media mensual (°C) de la
    temperatura media diaria, calculada de ``temperature_2m_max``/``_min``.
    Un mes incompleto (algún día sin dato) queda en ``None``: sumar solo los
    días presentes subestimaría la lluvia sin avisar.
    """
    tiempos = (diario or {}).get("time") or []
    lluvia = (diario or {}).get("precipitation_sum") or []
    maxima = (diario or {}).get("temperature_2m_max") or []
    minima = (diario or {}).get("temperature_2m_min") or []

    # Por (año, mes) se acumulan lluvia y temperaturas medias diarias.
    acumulado = {}
    for indice, texto in enumerate(tiempos):
        fecha = _fecha_de(texto)
        if fecha is None or not (anio_ini <= fecha.year <= anio_fin):
            continue
        clave = (fecha.year, fecha.month)
        fila = acumulado.setdefault(clave, {"lluvia": [], "tmax": [], "tmin": []})
        if indice < len(lluvia):
            fila["lluvia"].append(lluvia[indice])
        if indice < len(maxima):
            fila["tmax"].append(maxima[indice])
        if indice < len(minima):
            fila["tmin"].append(minima[indice])

    salida = {}
    for anio in range(anio_ini, anio_fin + 1):
        lluvias = []
        temperaturas = []
        for mes in range(1, 13):
            esperados = _dias_mes(anio, mes)
            fila = acumulado.get((anio, mes))

            lluvia_mm = None
            t2m = None
            if (fila is not None and len(fila["lluvia"]) == esperados
                    and all(v is not None for v in fila["lluvia"])):
                lluvia_mm = round(sum(fila["lluvia"]), 1)
            if (incluir_temperatura and fila is not None
                    and len(fila["tmax"]) == esperados
                    and len(fila["tmin"]) == esperados):
                medias = [
                    (a + b) / 2.0
                    for a, b in zip(fila["tmax"], fila["tmin"])
                    if a is not None and b is not None
                ]
                if len(medias) == esperados:
                    t2m = round(sum(medias) / len(medias), 1)
            lluvias.append(lluvia_mm)
            temperaturas.append(t2m)

        fila_anio = {"lluvia_mm": lluvias}
        if incluir_temperatura:
            fila_anio["t2m"] = temperaturas
        salida[str(anio)] = fila_anio
    return salida


def _valores_por_anio(climatologia, inicio, fin, clave, modo):
    """Valor de la ventana en cada año de la climatología.

    ``modo="suma"`` acumula (lluvia en mm); ``modo="media"`` pondera por días
    (temperatura en °C). Se **salta** el año si algún mes de la ventana no
    tiene dato: una anomalía a medias no es una anomalía.
    """
    if not climatologia:
        return []
    fracciones = _fracciones_ventana(inicio, fin)
    salida = []
    for anio_texto in sorted(climatologia):
        fila = (climatologia.get(anio_texto) or {}).get(clave)
        if not fila or len(fila) < 12:
            continue
        try:
            anio = int(anio_texto)
        except (TypeError, ValueError):
            continue
        total = 0.0
        peso = 0.0
        completo = True
        for mes, dias in fracciones.items():
            valor = fila[mes - 1]
            if valor is None:
                completo = False
                break
            fraccion = dias / _dias_mes(anio, mes)
            total += float(valor) * fraccion
            peso += fraccion
        if not completo or peso == 0:
            continue
        salida.append(total if modo == "suma" else total / peso)
    return salida


def normal_ventana(climatologia, inicio, fin):
    """Normal de lluvia (mm) para la ventana, repartiendo cada mes por días."""
    valores = _valores_por_anio(climatologia, inicio, fin, "lluvia_mm", "suma")
    if not valores:
        return {"lluvia_mm": None}
    return {"lluvia_mm": round(sum(valores) / len(valores), 1)}


def banda_por_anio(climatologia, inicio, fin):
    """``(P25, P75)`` de la lluvia de la ventana calculada año por año.

    ``None`` si no hay al menos dos años completos para comparar.
    """
    valores = _valores_por_anio(climatologia, inicio, fin, "lluvia_mm", "suma")
    if len(valores) < 2:
        return None
    return percentil(valores, 0.25), percentil(valores, 0.75)


def normal_ventana_temperatura(climatologia, inicio, fin):
    """Normal de temperatura (°C) de la ventana, ponderada por días."""
    valores = _valores_por_anio(climatologia, inicio, fin, "t2m", "media")
    if not valores:
        return None
    return round(sum(valores) / len(valores), 1)


def banda_por_anio_temperatura(climatologia, inicio, fin):
    """``(P25, P75)`` de la temperatura media de la ventana, año por año."""
    valores = _valores_por_anio(climatologia, inicio, fin, "t2m", "media")
    if len(valores) < 2:
        return None
    return percentil(valores, 0.25), percentil(valores, 0.75)


def _estado(valor, banda):
    """``por_debajo`` / ``normal`` / ``por_encima`` según la banda P25–P75."""
    if valor is None or not banda:
        return None
    bajo, alto = banda
    if bajo is None or alto is None:
        return None
    if valor < bajo:
        return "por_debajo"
    if valor > alto:
        return "por_encima"
    return "normal"


def anomalia_lluvia(acum, normal, banda):
    """Anomalía de lluvia: acumulado, normal, porcentaje y estado."""
    pct = None
    if acum is not None and normal:
        pct = round((float(acum) - float(normal)) / float(normal) * 100)
    return {
        "30d_mm": _red(acum),
        "normal_mm": _red(normal),
        "pct": pct,
        "banda": [_red(banda[0]), _red(banda[1])] if banda else None,
        "estado": _estado(acum, banda),
    }


def anomalia_temperatura(media, normal, banda):
    """Anomalía de temperatura: media, normal, delta y estado."""
    delta = None
    if media is not None and normal is not None:
        delta = float(media) - float(normal)
    return {
        "media": _red(media),
        "normal": _red(normal),
        "delta": _red(delta),
        "banda": [_red(banda[0]), _red(banda[1])] if banda else None,
        "estado": _estado(media, banda),
    }


def _medias_diarias(horas, fechas):
    """``{date: media}`` con solo los días que tienen las 24 horas."""
    por_dia = {}
    for indice, valor in enumerate(horas or []):
        if indice >= len(fechas or []):
            break
        dia = _fecha_de(fechas[indice])
        if dia is None:
            continue
        por_dia.setdefault(dia, []).append(valor)
    salida = {}
    for dia, valores in por_dia.items():
        if len(valores) == 24 and all(v is not None for v in valores):
            salida[dia] = sum(valores) / 24.0
    return salida


def anomalia_humedad(horas, fechas, ahora, zona="America/Santo_Domingo"):
    """Humedad superficial: media de los últimos 7 días y cambio contra los 7 previos.

    ``horas`` son los valores horarios y ``fechas`` sus marcas de tiempo (misma
    longitud y orden). La capa es 0–7 cm: no hay climatología comparable, por
    eso ``banda`` es siempre ``None``.
    """
    medias = _medias_diarias(horas, fechas)
    fin = _fecha_local(ahora, _zona(zona)) - dt.timedelta(days=1)
    ultimos = [medias.get(fin - dt.timedelta(days=i)) for i in range(DIAS_HUMEDAD)]
    anteriores = [
        medias.get(fin - dt.timedelta(days=i))
        for i in range(DIAS_HUMEDAD, DIAS_HUMEDAD * 2)
    ]
    valor = _media(ultimos)
    previa = _media(anteriores)
    cambio = None
    if valor is not None and previa is not None:
        cambio = valor - previa
    return {
        "valor": _red(valor, 3),
        "unidad": UNIDAD_HUMEDAD,
        "cambio_7d": _red(cambio, 3),
        "banda": None,
        "nota": NOTA_HUMEDAD,
    }


def construir_finca(finca, respuesta, climatologia, ahora):
    """Bloque de una finca del contrato de ``datos/reciente.json``.

    ``respuesta`` es el JSON de Open-Meteo o ``None``; ``climatologia`` es el
    bloque mensual de esa finca (``{"1991": {...}}``) o ``None``.
    """
    zona = _zona(finca)
    hoy = _fecha_local(ahora, zona)
    fin = hoy - dt.timedelta(days=1)
    inicio, fin = ventana(fin)
    nombre = finca.get("nombre") or finca.get("id") or "finca"
    respuesta = respuesta if isinstance(respuesta, dict) else {}
    avisos = []

    def avisar(texto):
        avisos.append(f"{nombre}: {texto}")

    daily = respuesta.get("daily") or {}
    hourly = respuesta.get("hourly") or {}
    unidades = respuesta.get("daily_units") or {}
    unidades_h = respuesta.get("hourly_units") or {}

    if not daily.get("time"):
        avisar("sin datos de Open-Meteo; la finca queda con null y sin pronóstico.")

    if unidades.get("precipitation_sum") not in (None, "mm"):
        avisar(
            "la unidad de precipitation_sum es "
            f"«{unidades.get('precipitation_sum')}», no mm; no se convirtió."
        )
    if ("soil_moisture_0_to_7cm" in (unidades_h or {})
            and unidades_h["soil_moisture_0_to_7cm"] not in UNIDADES_HUMEDAD):
        avisar(
            "la unidad de soil_moisture_0_to_7cm es "
            f"«{unidades_h['soil_moisture_0_to_7cm']}», no m³/m³; no se convirtió."
        )

    por_fecha = {}
    tiempos = daily.get("time") or []
    lluvia_d = daily.get("precipitation_sum") or []
    tmax_d = daily.get("temperature_2m_max") or []
    tmin_d = daily.get("temperature_2m_min") or []
    for indice, texto in enumerate(tiempos):
        fecha = _fecha_de(texto)
        if fecha is None:
            continue
        por_fecha[fecha] = {
            "lluvia_mm": lluvia_d[indice] if indice < len(lluvia_d) else None,
            "tmax": tmax_d[indice] if indice < len(tmax_d) else None,
            "tmin": tmin_d[indice] if indice < len(tmin_d) else None,
        }

    medias_humedad = _medias_diarias(
        hourly.get("soil_moisture_0_to_7cm") or [],
        hourly.get("time") or [],
    )

    serie = []
    dias_sin_lluvia = 0
    dias_sin_temperatura = 0
    dias_sin_humedad = 0
    for desplazamiento in range(DIAS_VENTANA):
        dia = inicio + dt.timedelta(days=desplazamiento)
        fila = por_fecha.get(dia) or {}
        lluvia = fila.get("lluvia_mm")
        tmax = fila.get("tmax")
        tmin = fila.get("tmin")
        humedad = medias_humedad.get(dia)
        if lluvia is None:
            dias_sin_lluvia += 1
        if tmax is None or tmin is None:
            dias_sin_temperatura += 1
        if humedad is None:
            dias_sin_humedad += 1
        serie.append({
            "fecha": dia.isoformat(),
            "lluvia_mm": _red(lluvia),
            "tmax": _red(tmax),
            "tmin": _red(tmin),
            "humedad": _red(humedad, 3),
        })

    if dias_sin_temperatura:
        avisar(
            "faltan datos de temperatura en "
            f"{dias_sin_temperatura} de los 30 días (null)."
        )
    if dias_sin_humedad:
        avisar(
            "faltan datos de humedad superficial en "
            f"{dias_sin_humedad} de los 30 días (null)."
        )

    pronostico = []
    for fecha in sorted(por_fecha):
        if fecha <= hoy:
            continue
        fila = por_fecha[fecha]
        pronostico.append({
            "fecha": fecha.isoformat(),
            "lluvia_mm": _red(fila.get("lluvia_mm")),
            "tmax": _red(fila.get("tmax")),
            "tmin": _red(fila.get("tmin")),
        })
        if len(pronostico) == DIAS_PRONOSTICO:
            break
    if not pronostico:
        avisar("sin pronóstico para los próximos días (lista vacía).")

    acumulado = None
    if dias_sin_lluvia:
        avisar(
            f"faltan datos de lluvia en {dias_sin_lluvia} de los 30 días; "
            "no se acumula la ventana (null)."
        )
    else:
        acumulado = sum(fila["lluvia_mm"] for fila in serie)

    normal = normal_ventana(climatologia, inicio, fin)["lluvia_mm"]
    banda = banda_por_anio(climatologia, inicio, fin)
    if climatologia and normal is None:
        avisar("normal de lluvia ERA5 incompleta; la anomalía queda sin calcular.")

    media_t = _media([
        (fila["tmax"] + fila["tmin"]) / 2.0
        for fila in serie
        if fila["tmax"] is not None and fila["tmin"] is not None
    ])
    normal_t = normal_ventana_temperatura(climatologia, inicio, fin)
    banda_t = banda_por_anio_temperatura(climatologia, inicio, fin)
    if media_t is not None and normal_t is None:
        avisar(
            "sin normal de temperatura ERA5 (t2m) en la climatología; "
            "la anomalía queda sin calcular."
        )

    humedad = anomalia_humedad(
        hourly.get("soil_moisture_0_to_7cm") or [],
        hourly.get("time") or [],
        ahora,
        zona=finca.get("zona_horaria") or "America/Santo_Domingo",
    )
    if humedad["valor"] is None:
        avisar("sin media de humedad superficial para los últimos 7 días (null).")

    return {
        "id": finca.get("id"),
        "nombre": nombre,
        "lluvia": anomalia_lluvia(acumulado, normal, banda),
        "temperatura": anomalia_temperatura(media_t, normal_t, banda_t),
        "humedad_superficial": humedad,
        "serie_30d": serie,
        "pronostico": pronostico,
        "avisos": avisos,
    }


def _mapa_climatologias(climatologias):
    """Acepta ``{id: mensual}`` o el archivo completo de climatología."""
    if not climatologias:
        return {}
    if isinstance(climatologias, dict) and "fincas" in climatologias:
        salida = {}
        for fila in climatologias.get("fincas") or []:
            if isinstance(fila, dict) and fila.get("id"):
                salida[fila["id"]] = fila.get("mensual") or {}
        return salida
    return climatologias


def construir_reciente(fincas, respuestas, climatologias, ahora):
    """Objeto completo de ``datos/reciente.json`` (contrato de la tarea 2)."""
    climas = _mapa_climatologias(climatologias)
    respuestas = respuestas or {}
    ahora = _ahora_consciente(ahora)

    if fincas:
        zona = _zona(fincas[0])
        actualizado = ahora.astimezone(zona).isoformat(timespec="seconds")
        hoy = _fecha_local(ahora, zona)
    else:
        actualizado = ahora.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
        hoy = ahora.date()
    inicio, fin = ventana(hoy - dt.timedelta(days=1))

    bloques = []
    avisos = []
    for finca in fincas:
        identificador = finca.get("id")
        bloque = construir_finca(
            finca,
            respuestas.get(identificador),
            climas.get(identificador),
            ahora,
        )
        avisos.extend(bloque.pop("avisos") or [])
        bloques.append(bloque)

    return {
        "version": VERSION,
        "actualizado": actualizado,
        "fuente": {
            "nombre": "Open-Meteo (ECMWF / ERA5-Land)",
            "url": "https://api.open-meteo.com/v1/forecast",
            "no_nasa": True,
            "nota": "No es NASA ni un sensor en la parcela: es modelo.",
        },
        "ventana": {
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
            "dias": DIAS_VENTANA,
        },
        "avisos": avisos,
        "fincas": bloques,
    }


def evaluar_frescura(actualizado, ahora):
    """Días entre ``actualizado`` y ``ahora``; aviso si pasa de 3 días."""
    fecha = None
    if isinstance(actualizado, dt.datetime):
        fecha = actualizado
    elif actualizado:
        try:
            fecha = dt.datetime.fromisoformat(str(actualizado).replace("Z", "+00:00"))
        except ValueError:
            fecha = None
    if fecha is None:
        return {"dias": None, "aviso": None}
    ahora = _ahora_consciente(ahora)
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=dt.timezone.utc)
    dias = (ahora.date() - fecha.astimezone(ahora.tzinfo).date()).days
    if dias < 0:
        dias = 0
    aviso = None
    if dias > 3:
        aviso = f"datos de hace {dias} días"
    return {"dias": dias, "aviso": aviso}


def leer_cache(ruta):
    """Lee el último ``reciente.json``; ``None`` si falta o está roto."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            objeto = json.load(archivo)
    except (OSError, ValueError):
        return None
    return objeto if isinstance(objeto, dict) else None


def escribir_atomico(ruta, objeto):
    """Escribe JSON con ``.tmp`` + ``os.replace`` (nunca deja un archivo a medias)."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    temporal = f"{ruta}.tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(objeto, archivo, ensure_ascii=False, indent=1)
        archivo.write("\n")
    os.replace(temporal, ruta)
