"""Genera la imagen satelital del mapa de la finca (para la demo "Mi parcela").

Descarga teselas de Esri World Imagery, las une y recorta una ventana centrada en
la finca. Escribe ``datos/mapa_<finca>.jpg`` y actualiza los metadatos del mapa
en ``datos/parcelas.json`` (metros por píxel, tamaño, centro).

Es imagen de satélite real de la zona: NO es NASA y se acredita en la interfaz.
Las parcelas que se dibujan encima son simuladas.

Uso:
    python3 tools/generar_mapa_parcela.py
    python3 tools/generar_mapa_parcela.py --zoom 17 --size 1024
"""

from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
import urllib.request

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
TESELA = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
TAM_TESELA = 256
ZOOM_DEFECTO = 17
TAM_DEFECTO = 1024
USER_AGENT = "tierra-spaceapps/1.0 (demo educativa)"


def mundo_a_pixel(lat, lon, zoom, tam_tesela=TAM_TESELA):
    """Píxel global (Web Mercator) del punto en ese zoom."""
    n = 2 ** zoom
    px = (lon + 180.0) / 360.0 * n * tam_tesela
    r = math.radians(lat)
    py = (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n * tam_tesela
    return px, py


def metros_por_pixel(lat, zoom, tam_tesela=TAM_TESELA):
    """Escala real a esa latitud (Web Mercator corrige por coseno)."""
    return math.cos(math.radians(lat)) * 2 * math.pi * 6378137 / (tam_tesela * 2 ** zoom)


def descargar(z, x, y):
    url = TESELA.format(z=z, y=y, x=x)
    peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return Image.open(io.BytesIO(respuesta.read())).convert("RGB")


def construir(lat, lon, zoom, tam):
    px, py = mundo_a_pixel(lat, lon, zoom)
    izquierda, arriba = px - tam / 2, py - tam / 2
    x0, y0 = int(math.floor(izquierda / TAM_TESELA)), int(math.floor(arriba / TAM_TESELA))
    x1, y1 = int(math.floor((izquierda + tam - 1) / TAM_TESELA)), int(math.floor((arriba + tam - 1) / TAM_TESELA))

    lienzo = Image.new("RGB", ((x1 - x0 + 1) * TAM_TESELA, (y1 - y0 + 1) * TAM_TESELA))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            try:
                lienzo.paste(descargar(zoom, x, y), ((x - x0) * TAM_TESELA, (y - y0) * TAM_TESELA))
                print(f"  tesela {zoom}/{y}/{x} ok", flush=True)
            except Exception as error:  # una tesela caída deja hueco, no rompe la imagen
                print(f"  tesela {zoom}/{y}/{x} FALLA: {error!r}"[:90], flush=True)

    recorte_x = int(round(izquierda - x0 * TAM_TESELA))
    recorte_y = int(round(arriba - y0 * TAM_TESELA))
    return lienzo.crop((recorte_x, recorte_y, recorte_x + tam, recorte_y + tam))


def main():
    analizador = argparse.ArgumentParser(description="Mapa satelital de la finca")
    analizador.add_argument("--finca", default="constanza")
    analizador.add_argument("--lat", type=float, default=18.91)
    analizador.add_argument("--lon", type=float, default=-70.74)
    analizador.add_argument("--zoom", type=int, default=ZOOM_DEFECTO)
    analizador.add_argument("--size", type=int, default=TAM_DEFECTO)
    argumentos = analizador.parse_args()

    DATOS.mkdir(exist_ok=True)
    print(f"Mapa de {argumentos.finca} a zoom {argumentos.zoom}...", flush=True)
    imagen = construir(argumentos.lat, argumentos.lon, argumentos.zoom, argumentos.size)

    destino = DATOS / f"mapa_{argumentos.finca}.jpg"
    imagen.save(destino, "JPEG", quality=82, optimize=True, progressive=True)
    escala = metros_por_pixel(argumentos.lat, argumentos.zoom)
    print(f"escrito {destino.name}: {imagen.width}x{imagen.height} px · "
          f"{escala:.3f} m/px · {imagen.width * escala:.0f} m de lado")

    ruta = DATOS / "parcelas.json"
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    documento["mapa"] = {
        "archivo": destino.name,
        "zoom": argumentos.zoom,
        "centro": {"lat": argumentos.lat, "lon": argumentos.lon},
        "ancho_px": imagen.width,
        "alto_px": imagen.height,
        "metros_por_pixel": round(escala, 4),
        "fuente": "Esri World Imagery (imagen satelital) · no NASA",
    }
    ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATOS / "parcelas.js").write_text(
        "window.__PARCELAS__ = " + json.dumps(documento, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    print("parcelas.json y parcelas.js actualizados con los metadatos del mapa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
