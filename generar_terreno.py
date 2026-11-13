"""Terreno de la finca con SRTM (NASA) vía tiles Terrarium públicos.

Descarga los tiles de elevación alrededor de la finca, calcula pendiente y un
proxy de riesgo de erosión, y escribe ``datos/terreno.json`` + ``.js`` para que la
app funcione sin red.

Honestidad: los tiles son Terrarium (codifican SRTM); la pendiente la calcula esta
demo a partir de ellos. Un 15 % de pendiente es un umbral orientativo, no un
modelo de erosión.

Uso:
    python3 generar_terreno.py
    python3 generar_terreno.py --revisar
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import math
import pathlib
import sys

import requests
from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
TESELA = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 14
LADO_PX = 160
PENDIENTE_ALTA = 15.0
USER_AGENT = "tierra-spaceapps/1.0 (demo educativa)"


def tile_xy(lat, lon, zoom):
    total = 2 ** zoom
    x = (lon + 180.0) / 360.0 * total
    radianes = math.radians(lat)
    y = (1.0 - math.log(math.tan(radianes) + 1 / math.cos(radianes)) / math.pi) / 2.0 * total
    return x, y


def metros_por_pixel(lat, zoom):
    return math.cos(math.radians(lat)) * 2 * math.pi * 6378137 / (256 * 2 ** zoom)


def decodificar_elevacion(rgb):
    """Terrarium: altura = R*256 + G + B/256 - 32768 (metros)."""
    r, g, b = rgb[:3]
    return r * 256 + g + b / 256 - 32768


def pendientes(elevaciones, metros):
    """Matriz de pendientes en grados a partir de una matriz de elevaciones."""
    alto = len(elevaciones)
    ancho = len(elevaciones[0])
    salida = []
    for y in range(alto):
        fila = []
        for x in range(ancho):
            x0 = max(0, x - 1)
            x1 = min(ancho - 1, x + 1)
            y0 = max(0, y - 1)
            y1 = min(alto - 1, y + 1)
            dzdx = (elevaciones[y][x1] - elevaciones[y][x0]) / max(1, (x1 - x0))
            dzdy = (elevaciones[y1][x] - elevaciones[y0][x]) / max(1, (y1 - y0))
            pendiente = math.degrees(math.atan(math.hypot(dzdx, dzdy) / metros))
            fila.append(pendiente)
        salida.append(fila)
    return salida


def resumen(elevaciones, metros):
    planas = [valor for fila in elevaciones for valor in fila]
    pend = pendientes(elevaciones, metros)
    valores = [valor for fila in pend for valor in fila]
    altas = sum(1 for valor in valores if valor >= PENDIENTE_ALTA)
    return {
        "elevacion_media_m": round(sum(planas) / len(planas)),
        "elevacion_min_m": round(min(planas)),
        "elevacion_max_m": round(max(planas)),
        "pendiente_media_deg": round(sum(valores) / len(valores), 1),
        "pendiente_max_deg": round(max(valores), 1),
        "pendiente_alta_pct": round(100.0 * altas / len(valores), 1),
        "umbral_pendiente_deg": PENDIENTE_ALTA,
    }


def descargar(z, x, y):
    peticion = requests.get(TESELA.format(z=z, x=x, y=y),
                            headers={"User-Agent": USER_AGENT}, timeout=120)
    peticion.raise_for_status()
    return Image.open(io.BytesIO(peticion.content)).convert("RGB")


def construir(lat, lon):
    x, y = tile_xy(lat, lon, ZOOM)
    xt, yt = int(x), int(y)
    px = int((x - xt) * 256)
    py = int((y - yt) * 256)
    mitad = LADO_PX // 2
    izquierda, arriba = xt * 256 + px - mitad, yt * 256 + py - mitad
    x0, y0 = math.floor(izquierda / 256), math.floor(arriba / 256)
    x1, y1 = math.floor((izquierda + LADO_PX - 1) / 256), math.floor((arriba + LADO_PX - 1) / 256)
    lienzo = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    for tile_x in range(x0, x1 + 1):
        for tile_y in range(y0, y1 + 1):
            lienzo.paste(descargar(ZOOM, tile_x, tile_y),
                         ((tile_x - x0) * 256, (tile_y - y0) * 256))
    recorte = lienzo.crop((izquierda - x0 * 256, arriba - y0 * 256,
                           izquierda - x0 * 256 + LADO_PX,
                           arriba - y0 * 256 + LADO_PX))
    metros = metros_por_pixel(lat, ZOOM)
    elevaciones = [[decodificar_elevacion(recorte.getpixel((x, y)))
                    for x in range(recorte.width)]
                   for y in range(recorte.height)]
    datos = resumen(elevaciones, metros)
    datos["metros_por_pixel"] = round(metros, 1)
    return datos


def escribir(datos):
    (DATOS / "terreno.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATOS / "terreno.js").write_text(
        "window.__TERRENO__ = " + json.dumps(datos, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    print("escrito datos/terreno.json:", datos["elevacion_media_m"], "m ·",
          datos["pendiente_media_deg"], "° de pendiente media")


def revisar():
    ruta = DATOS / "terreno.json"
    if not ruta.exists():
        print("falta datos/terreno.json: corre python3 generar_terreno.py")
        return 1
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    print("OK" if datos.get("pendiente_media_deg") is not None else "sin pendiente")
    return 0 if datos.get("pendiente_media_deg") is not None else 1


def main():
    analizador = argparse.ArgumentParser(description="Terreno SRTM y pendiente de la finca")
    analizador.add_argument("--revisar", action="store_true")
    opciones = analizador.parse_args()
    if opciones.revisar:
        return revisar()
    parcelas = json.loads((DATOS / "parcelas.json").read_text(encoding="utf-8"))
    centro = (parcelas.get("mapa") or {}).get("centro") or {}
    lat = float(centro.get("lat", 18.9045))
    lon = float(centro.get("lon", -70.716))
    escribir({
        "version": 1,
        "generado": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "centro": {"lat": lat, "lon": lon},
        "fuente": "SRTM (NASA) vía tiles Terrarium públicos",
        "nota": ("Pendiente calculada por la demo a partir de SRTM; el umbral de "
                 + f"{PENDIENTE_ALTA:.0f}° es orientativo, no un modelo de erosión."),
        **construir(lat, lon),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
