"""Genera ``datos/fincas.json``: climatología mensual POWER de las fincas piloto.

Es la lente NASA de largo plazo (1991–2020) que usan el motor de rotaciones y la
interfaz. La lluvia de POWER viene como tasa media diaria (mm/día), no como
total del mes.

Uso:
    python3 generar_fincas.py --verificar   # 3 líneas de control, no escribe
    python3 generar_fincas.py               # escribe datos/fincas.json
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.power_cliente import ErrorPower, descargar_mensual

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

RAIZ = Path(__file__).resolve().parent
SALIDA_POR_DEFECTO = RAIZ / "datos" / "fincas.json"

ANIO_INI = 1991
ANIO_FIN = 2020
ANIO_MINIMO = 1981  # primer año de la API mensual de POWER
VARIABLES = ("PRECTOTCORR", "T2M")
ZONA_HORARIA = "America/Santo_Domingo"
FUENTE = "NASA POWER temporal/monthly/point · community AG · reanálisis MERRA-2"
FUENTE_CLIMATOLOGIA = "NASA POWER (reanálisis MERRA-2)"
PAIS = "República Dominicana"
DECIMALES = 2

# Coordenadas ya usadas en validar_power.py: no inventar otras.
FINCAS = (
    {
        "id": "constanza",
        "nombre": "Constanza",
        "pais": PAIS,
        "lat": 18.91,
        "lon": -70.74,
        "zona_horaria": ZONA_HORARIA,
        "cultivo_actual": "provisional",
    },
    {
        "id": "azua",
        "nombre": "Azua",
        "pais": PAIS,
        "lat": 18.45,
        "lon": -70.73,
        "zona_horaria": ZONA_HORARIA,
        "cultivo_actual": "provisional",
    },
    {
        "id": "san_francisco_de_macoris",
        "nombre": "San Francisco de Macorís",
        "pais": PAIS,
        "lat": 19.30,
        "lon": -70.25,
        "zona_horaria": ZONA_HORARIA,
        "cultivo_actual": "provisional",
    },
)


def _redondear(valor):
    """Redondea un dato de POWER sin convertir un hueco en 0."""
    return None if valor is None else round(valor, DECIMALES)


def construir_finca(finca, mensual):
    """Finca lista para el JSON a partir de ``parsear_mensual`` (puro)."""
    lluvia = mensual.get("PRECTOTCORR") or {}
    temperatura = mensual.get("T2M") or {}
    anios = sorted(set(lluvia) | set(temperatura))
    if not anios:
        raise ValueError(f"{finca['id']}: POWER no devolvió datos mensuales.")

    por_anio = {}
    for anio in anios:
        fila_lluvia = lluvia.get(anio) or {}
        fila_t2m = temperatura.get(anio) or {}
        por_anio[str(anio)] = {
            "lluvia_mm_dia": [
                _redondear(fila_lluvia.get(mes)) for mes in range(1, 13)
            ],
            "t2m": [_redondear(fila_t2m.get(mes)) for mes in range(1, 13)],
        }

    salida = dict(finca)
    salida["climatologia"] = {
        "periodo": [anios[0], anios[-1]],
        "fuente": FUENTE_CLIMATOLOGIA,
        "mensual": por_anio,
    }
    return salida


def resumen_climatologia(climatologia):
    """Lluvia media anual (mm) y T media anual (°C) de una finca ya construida.

    Los años con algún mes en ``null`` no entran en la media: no se inventa el
    hueco. Si no queda ningún año completo, ambos valores son ``None``.
    """
    lluvia_anual = []
    temperatura_anual = []
    for anio, valores in sorted(climatologia["mensual"].items()):
        dias = [calendar.monthrange(int(anio), mes)[1] for mes in range(1, 13)]
        lluvia = valores["lluvia_mm_dia"]
        t2m = valores["t2m"]
        if all(valor is not None for valor in lluvia):
            lluvia_anual.append(sum(v * d for v, d in zip(lluvia, dias)))
        if all(valor is not None for valor in t2m):
            temperatura_anual.append(sum(t2m) / 12)

    return {
        "lluvia_anual_mm": (
            round(sum(lluvia_anual) / len(lluvia_anual), 1) if lluvia_anual else None
        ),
        "t2m_media": (
            round(sum(temperatura_anual) / len(temperatura_anual), 1)
            if temperatura_anual else None
        ),
        "anios_completos": len(temperatura_anual),
    }


def ahora_local():
    """ISO 8601 con el offset de la zona de las fincas."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(ZONA_HORARIA)).isoformat(timespec="seconds")
        except Exception:  # sin base de zonas horarias instalada
            pass
    return datetime.now(timezone(timedelta(hours=-4))).isoformat(timespec="seconds")


def generar(desde, hasta):
    """Descarga las tres fincas; si una falla, la excepción sube y no se escribe."""
    fincas = []
    for finca in FINCAS:
        print(f"  POWER · {finca['nombre']}", file=sys.stderr, flush=True)
        mensual = descargar_mensual(
            finca["lat"], finca["lon"], list(VARIABLES), desde, hasta
        )
        fincas.append(construir_finca(finca, mensual))

    return {
        "version": 1,
        "generado": ahora_local(),
        "fuente": FUENTE,
        "periodo": [desde, hasta],
        "fincas": fincas,
    }


def escribir(destino, datos):
    """Escribe el JSON de forma atómica (nunca deja un archivo a medias)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=1)
        archivo.write("\n")
    os.replace(temporal, destino)


def _linea_finca(finca):
    resumen = resumen_climatologia(finca["climatologia"])
    lluvia = resumen["lluvia_anual_mm"]
    temperatura = resumen["t2m_media"]
    texto_lluvia = f"{lluvia:7.1f} mm/año" if lluvia is not None else "  sin datos"
    texto_temperatura = f"{temperatura:.1f} °C" if temperatura is not None else "sin datos"
    return (
        f"{finca['nombre']:<24} {texto_lluvia} · T media {texto_temperatura}"
        f" · {resumen['anios_completos']} años completos"
    )


def main(argv=None):
    analizador = argparse.ArgumentParser(
        description="Climatología mensual POWER 1991–2020 de las fincas piloto."
    )
    analizador.add_argument(
        "--verificar",
        action="store_true",
        help="imprime el resumen de cada finca y no escribe nada",
    )
    analizador.add_argument(
        "--salida",
        type=Path,
        default=SALIDA_POR_DEFECTO,
        help="ruta del JSON de salida (por defecto datos/fincas.json)",
    )
    analizador.add_argument("--desde", type=int, default=ANIO_INI)
    analizador.add_argument("--hasta", type=int, default=ANIO_FIN)
    args = analizador.parse_args(argv)

    anio_actual = datetime.now().year
    if not ANIO_MINIMO <= args.desde <= args.hasta <= anio_actual:
        analizador.error(
            f"periodo no válido: {args.desde}–{args.hasta}"
            f" (POWER mensual va de {ANIO_MINIMO} a {anio_actual})"
        )

    try:
        datos = generar(args.desde, args.hasta)
    except (ErrorPower, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("No se escribió nada.", file=sys.stderr)
        return 1

    if args.verificar:
        for finca in datos["fincas"]:
            print(_linea_finca(finca))
        return 0

    escribir(args.salida, datos)
    for finca in datos["fincas"]:
        print(_linea_finca(finca))
    tamano = args.salida.stat().st_size / 1024
    print(
        f"Escrito {args.salida.relative_to(RAIZ) if args.salida.is_relative_to(RAIZ) else args.salida}"
        f" · {len(datos['fincas'])} fincas · {args.desde}–{args.hasta}"
        f" · {tamano:.1f} KB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
