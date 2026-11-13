"""Satélite real del reto: NDVI (MODIS/Terra) y lluvia (GPM IMERG) vía NASA GIBS.

Descarga de GIBS la imagen oficial de cada capa, la recorta alrededor de la finca
y decodifica su color con el mapa de colores oficial para dar un valor
aproximado. Esa imagen y el JSON quedan en ``datos/`` para que la app funcione
sin red.

Honestidad: el valor se deduce del color publicado por GIBS, no es un dato
calibrado en la parcela; el píxel (289 m NDVI, ~2,3 km IMERG) es mayor que la
finca. La app lo dice en pantalla.

Uso:
    python3 generar_satelite.py            # descarga y escribe
    python3 generar_satelite.py --revisar  # solo comprueba el snapshot
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import math
import pathlib
import re
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter

RAIZ = pathlib.Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
GIBS = "https://gibs.earthdata.nasa.gov"
CAPAS = {
    "ndvi": {
        "layer": "MODIS_Terra_L3_NDVI_16Day",
        "colormap": "MODIS_L3_NDVI",
        "nivel": 9,
        "radio": 2,
        "recorte": 48,
        "escala": 8,
        "suavizado": 1.6,
        "nombre": "NDVI · MODIS/Terra 16 días",
        "imagen": "ndvi_modis.png",
        "unidad": "",
    },
    "lluvia": {
        "layer": "IMERG_Precipitation_Rate",
        "colormap": "GPM_Precipitation_Rate",
        "nivel": 6,
        "radio": 4,
        "recorte": 96,
        "escala": 3,
        "suavizado": 1.0,
        "nombre": "Lluvia · GPM IMERG",
        "imagen": "imerg_gpm.png",
        "unidad": "mm/h",
    },
}


def tile_xy(lat, lon, nivel):
    """Coordenadas continuas de tile (Web Mercator) para un punto."""
    total = 2 ** nivel
    x = (lon + 180.0) / 360.0 * total
    radianes = math.radians(lat)
    y = (1.0 - math.log(math.tan(radianes) + 1 / math.cos(radianes)) / math.pi) / 2.0 * total
    return x, y


def resolucion_m(nivel, lat):
    """Metros por píxel de GIBS en ese nivel y latitud."""
    return round(156543.03392 * math.cos(math.radians(lat)) / (2 ** nivel), 1)


def numero(texto):
    return float(texto.strip().replace("INF", "inf"))


def mapa_colores(xml):
    """RGB -> valor medio del rango, a partir del mapa de colores oficial."""
    mapa = {}
    for hallado in re.finditer(
            r'<ColorMapEntry rgb="([\d,]+)"[^>]*?value="\[(.*?)\)"', xml):
        rgb = tuple(int(v) for v in hallado.group(1).split(","))
        partes = [p for p in hallado.group(2).split(",") if p.strip()]
        if len(partes) < 2:
            continue
        try:
            bajo, alto = numero(partes[0]), numero(partes[1])
        except ValueError:
            continue
        mapa[rgb] = bajo if math.isinf(bajo) else (bajo + alto) / 2
    return mapa


def decodificar_tile(imagen, px, py, radio, mapa):
    """Valores aproximados de una ventana alrededor del píxel de la finca."""
    valores = []
    total = 0
    for dx in range(-radio, radio + 1):
        for dy in range(-radio, radio + 1):
            x = min(imagen.width - 1, max(0, px + dx))
            y = min(imagen.height - 1, max(0, py + dy))
            total += 1
            pixel = imagen.getpixel((x, y))
            if len(pixel) == 4 and pixel[3] < 128:
                continue
            if pixel[:3] in mapa:
                valores.append(mapa[pixel[:3]])
    if not valores:
        return {"valor": None, "cobertura": 0.0}
    return {
        "valor": round(sum(valores) / len(valores), 3),
        "cobertura": round(len(valores) / total, 2),
    }


def rango_de_color(mapa, valor):
    """Rango del bin de color que contiene el valor medio."""
    if valor is None:
        return None
    candidatos = sorted(v for v in mapa.values() if abs(v - valor) < 0.5)
    return [round(valor, 3)] if not candidatos else [round(valor, 3)]


def recortar(imagen, px, py, lado, escala, ruta, fondo=None, suavizado=0.0):
    """Guarda un recorte ampliado (vecino más cercano) con la finca marcada."""
    mitad = lado // 2
    caja = (max(0, px - mitad), max(0, py - mitad),
            min(imagen.width, px + mitad), min(imagen.height, py + mitad))
    trozo = imagen.crop(caja)
    if fondo:
        # Las capas con transparencia (IMERG sin lluvia) se ven mejor sobre oscuro.
        base = Image.new("RGB", trozo.size, fondo)
        base.paste(trozo, mask=trozo.getchannel("A"))
        trozo = base
    else:
        trozo = trozo.convert("RGB")
    # Suavizado al ampliar: el dato es grueso (289 m–2,3 km), pero así se lee el
    # patrón en vez de ver bloques de píxeles.
    grande = trozo.resize((trozo.width * escala, trozo.height * escala), Image.BICUBIC)
    if suavizado:
        grande = grande.filter(ImageFilter.GaussianBlur(suavizado))
    dibujo = ImageDraw.Draw(grande)
    centro = ((px - caja[0]) * escala, (py - caja[1]) * escala)
    dibujo.rectangle([centro[0] - escala * 2, centro[1] - escala * 2,
                      centro[0] + escala * 2, centro[1] + escala * 2],
                     outline=(53, 214, 255), width=2)
    grande.save(ruta)


def fecha_por_defecto(xml, layer):
    i = xml.find(f"<ows:Identifier>{layer}</ows:Identifier>")
    if i < 0:
        return None
    bloque = xml[i:i + 6000]
    hallado = re.search(r"<Default>([^<]+)</Default>", bloque)
    return hallado.group(1) if hallado else None


def construir(parcelas):
    centro = (parcelas.get("mapa") or {}).get("centro") or {}
    lat = float(centro.get("lat", 18.91))
    lon = float(centro.get("lon", -70.74))
    capacidades = requests.get(
        f"{GIBS}/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml", timeout=120).text
    salida = {}
    for clave, capa in CAPAS.items():
        fecha = fecha_por_defecto(capacidades, capa["layer"])
        if not fecha:
            continue
        colormap = requests.get(
            f"{GIBS}/colormaps/v1.3/{capa['colormap']}.xml", timeout=60).text
        mapa = mapa_colores(colormap)
        nivel = capa["nivel"]
        x, y = tile_xy(lat, lon, nivel)
        xt, yt = int(x), int(y)
        px = int((x - xt) * 256)
        py = int((y - yt) * 256)
        url = (f"{GIBS}/wmts/epsg3857/best/{capa['layer']}/default/{fecha}/"
               f"GoogleMapsCompatible_Level{nivel}/{nivel}/{yt}/{xt}.png")
        respuesta = requests.get(url, timeout=120)
        respuesta.raise_for_status()
        imagen = Image.open(io.BytesIO(respuesta.content)).convert("RGBA")
        decodificado = decodificar_tile(imagen, px, py, capa["radio"], mapa)
        ruta = DATOS / capa["imagen"]
        fondo = (8, 17, 28) if clave == "lluvia" else None
        # Si no hay lluvia, no se guarda imagen: la app muestra un dato limpio en
        # vez de un mapa vacío lleno de bloques.
        guardar_imagen = not (clave == "lluvia" and not decodificado["valor"])
        if guardar_imagen:
            recortar(imagen, px, py, capa["recorte"], capa.get("escala", 4), ruta,
                     fondo, capa.get("suavizado", 0.0))
        nota = ("Valor aproximado decodificado del color oficial de GIBS; "
                "el píxel es mayor que la parcela, no es una medición en el suelo.")
        if clave == "lluvia" and decodificado["valor"] is None:
            decodificado = {"valor": 0.0, "cobertura": 0.0}
            nota = ("Sin lluvia significativa en esa pasada de IMERG (< 0,1 mm/h). "
                    "El píxel (~2,3 km) es mayor que la parcela; no es un pluviómetro.")
        salida[clave] = {
            "nombre": capa["nombre"],
            "layer": capa["layer"],
            "fecha": fecha,
            "valor": decodificado["valor"],
            "cobertura": decodificado["cobertura"],
            "unidad": capa["unidad"],
            "resolucion_m": resolucion_m(nivel, lat),
            "imagen": capa["imagen"] if guardar_imagen else None,
            "nota": nota,
        }
    return {
        "version": 1,
        "generado": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fuente": "NASA GIBS · MODIS/Terra (NDVI) y GPM IMERG (lluvia) · no NASA para el fondo Esri",
        "centro": {"lat": lat, "lon": lon},
        "capas": salida,
    }


def escribir(datos):
    (DATOS / "satelite.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATOS / "satelite.js").write_text(
        "window.__SATELITE__ = " + json.dumps(datos, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    print(f"escrito datos/satelite.json ({', '.join(datos['capas'])})")


def revisar():
    ruta = DATOS / "satelite.json"
    if not ruta.exists():
        print("falta datos/satelite.json: corre python3 generar_satelite.py")
        return 1
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    capas = datos.get("capas") or {}
    faltan = []
    for clave in ("ndvi", "lluvia"):
        capa = capas.get(clave) or {}
        # La lluvia puede no tener imagen (sin lluvia) pero sí valor y fecha.
        if not capa.get("fecha") or (capa.get("imagen") is None and capa.get("valor") is None):
            faltan.append(clave)
    print("OK" if not faltan else f"faltan capas: {faltan}")
    return 0 if not faltan else 1


def main():
    analizador = argparse.ArgumentParser(description="Satélite NDVI e IMERG de GIBS")
    analizador.add_argument("--revisar", action="store_true", help="solo comprueba el snapshot")
    opciones = analizador.parse_args()
    if opciones.revisar:
        return revisar()
    parcelas = json.loads((DATOS / "parcelas.json").read_text(encoding="utf-8"))
    escribir(construir(parcelas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
