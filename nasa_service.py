"""Servicio de datos NASA para el globo Tierra.

Consulta varias fuentes en segundo plano para no bloquear el render:
- EONET: eventos naturales activos o históricos.
- NeoWs: asteroides cercanos a la Tierra.
- APOD: imagen astronómica del día.
- NASA GIBS/Worldview: comparación satelital Antes/Después por evento.
- Celestrak: TLE oficiales y propagación orbital en vivo (ISS, Hubble,
  Terra, Aqua, Suomi NPP, Landsat 8/9 y NOAA-20).

Las funciones de este módulo devuelven listas, diccionarios o bytes; no
importan Pygame. La interfaz consume los resultados con ``poll()``.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import io
import json
import math
import os
import queue
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps

DIR = Path(__file__).resolve().parent

# La clave vive en tierra/.env. El .env raíz queda como respaldo para no
# duplicar configuración si se ejecuta desde la raíz del repositorio.
load_dotenv(DIR / ".env", override=False)
load_dotenv(DIR.parent / ".env", override=False)

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
EONET_MODOS = {
    "activos": {"status": "open", "dias": 7},
    "historicos": {"status": "all", "dias": 30},
}
NEOWS_URL = "https://api.nasa.gov/neo/rest/v1/feed"
APOD_URL = "https://api.nasa.gov/planetary/apod"
APOD_WEB_URL = "https://science.nasa.gov/apod/"
GIBS_SNAPSHOT_URL = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"

USER_AGENT = "tierra-nasa-monitor/1.0"
TIMEOUT = (6, 15)
MAX_IMAGEN_BYTES = 16 * 1024 * 1024
THUMB_SIZE = (320, 180)

SAT_SIZE = 1024
SAT_ANALYSIS_SIZE = 256
SAT_DELTA = 1.0
SAT_RECORTE = 2.0 * SAT_DELTA
SAT_RECORTES = (2.0, 1.0, 0.5)
SAT_THRESHOLD = 28.0
SAT_MIN_COBERTURA = 0.35
SAT_TIMEOUT = (10, 45)
SAT_CAPAS = (
    "MODIS_Terra_CorrectedReflectance_TrueColor",
    "MODIS_Aqua_CorrectedReflectance_TrueColor",
    "VIIRS_SNPP_CorrectedReflectance_TrueColor",
    "VIIRS_NOAA20_CorrectedReflectance_TrueColor",
    "VIIRS_NOAA21_CorrectedReflectance_TrueColor",
)

# --- Seguimiento orbital en tiempo real (Celestrak TLE) ---
CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_GRUPOS = ("stations", "science", "resource", "weather")
CELESTRAK_PAUSA = 1.1
TLE_TTL = 2 * 60 * 60.0
TLE_REINTENTO = 60.0
TLE_CACHE_PATH = DIR / "cache" / "tle.json"
TLE_CACHE_MAX_EDAD = 24 * 60 * 60.0
MU_TIERRA = 398600.4418
RADIO_TIERRA_KM = 6371.0088
RADIO_ECUATORIAL_KM = 6378.137
APLASTAMIENTO_TIERRA = 1.0 / 298.257223563
EXCENTRICIDAD_TIERRA = APLASTAMIENTO_TIERRA * (2.0 - APLASTAMIENTO_TIERRA)
J2_TIERRA = 1.08262668e-3

# Satélites emblemáticos de NASA/NOAA. Los nombres y colores son de la UI;
# la designación oficial llega desde el TLE de Celestrak.
SATELITES_NASA = (
    {"catnr": 25544, "nombre": "ISS (EEI)", "grupo": "Estación",
     "color": (255, 214, 120)},
    {"catnr": 20580, "nombre": "Hubble", "grupo": "Ciencia",
     "color": (198, 168, 255)},
    {"catnr": 25994, "nombre": "Terra", "grupo": "Recursos",
     "color": (120, 232, 168)},
    {"catnr": 27424, "nombre": "Aqua", "grupo": "Recursos",
     "color": (110, 198, 255)},
    {"catnr": 37849, "nombre": "Suomi NPP", "grupo": "Meteorología",
     "color": (150, 224, 255)},
    {"catnr": 39084, "nombre": "Landsat 8", "grupo": "Recursos",
     "color": (255, 196, 120)},
    {"catnr": 49260, "nombre": "Landsat 9", "grupo": "Recursos",
     "color": (255, 160, 140)},
    {"catnr": 43013, "nombre": "NOAA-20", "grupo": "Meteorología",
     "color": (170, 236, 255)},
)

try:
    from sgp4.api import Satrec as _Satrec, jday as _jday
except ImportError:
    _Satrec = None
    _jday = None

# Limita el tamaño de imágenes APOD que Pillow intentará decodificar.
Image.MAX_IMAGE_PIXELS = 40_000_000


class NasaError(Exception):
    """Error de red o de datos con un mensaje apto para mostrar en la UI."""


class SateliteSinCobertura(NasaError):
    """La capa/fecha no tiene una imagen satelital utilizable."""


class EventosEonet(list):
    """Lista de eventos EONET con el contexto de la consulta.

    Hereda de ``list`` para conservar la compatibilidad con el visor anterior:
    se puede iterar, indexar y medir como una lista normal. Los metadatos
    permiten que la interfaz sepa si el resultado es de ``activos`` o de
    ``historicos`` y evite mostrar respuestas viejas al cambiar de modo.
    """

    def __init__(self, eventos, modo, dias, status):
        super().__init__(eventos)
        self.modo = modo
        self.dias = dias
        self.status = status


def _f(valor, defecto=None):
    """Convierte a float sin romper la consulta si el campo falta."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _i(valor, defecto=0):
    """Convierte a int sin romper la consulta si el campo falta."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _texto(valor, defecto=""):
    """Devuelve un string limpio para campos opcionales de la API."""
    return valor.strip() if isinstance(valor, str) else defecto


def _fecha_corta(valor):
    """Extrae ``YYYY-MM-DD`` de una fecha ISO 8601 de EONET."""
    return valor[:10] if isinstance(valor, str) else ""


def _fecha_evento(evento):
    """Fecha del evento EONET como ``datetime.date``."""
    valor = evento.get("fecha") if isinstance(evento, dict) else ""
    if not valor:
        raise NasaError("El evento no tiene fecha para la comparación satelital.")
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise NasaError("La fecha del evento no es válida para la comparación satelital.") from None


def _fecha_evento_inicio(evento):
    """Primera fecha conocida del evento; respaldo para cachés antiguas."""
    valor = evento.get("fecha_inicio") if isinstance(evento, dict) else ""
    if not valor:
        return _fecha_evento(evento)
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return _fecha_evento(evento)


def _fechas_satelite(evento):
    """Antes = inicio-2; Después = fin+1 o fin, sin superar hoy."""
    fecha_inicio = _fecha_evento_inicio(evento)
    fecha_fin = _fecha_evento(evento)
    hoy = dt.date.today()
    antes = fecha_inicio - dt.timedelta(days=2)
    if antes > hoy:
        raise NasaError("El evento todavía no tiene dos días de historial satelital.")

    despues = []
    for delta in (1, 0):
        candidato = fecha_fin + dt.timedelta(days=delta)
        if candidato <= hoy and candidato not in despues:
            despues.append(candidato)
    if not despues:
        raise NasaError("El evento todavía no tiene una fecha satelital disponible.")
    return antes, despues


def _bbox_satelite(lat, lon, recorte=SAT_RECORTE):
    """Caja geográfica del recorte pedido, desplazada si toca el antimeridiano.

    ``recorte`` es el ancho total en grados. Los niveles pequeños permiten una
    vista más cercana, aunque el detalle real sigue limitado por la resolución
    nativa de MODIS/VIIRS.
    """
    recorte = max(0.1, min(20.0, _f(recorte, SAT_RECORTE)))
    mitad = recorte / 2.0
    lat = max(-90.0 + mitad, min(90.0 - mitad, _f(lat, 0.0)))
    lon = _f(lon, 0.0)
    if lon - mitad < -180.0:
        lon = -180.0 + mitad
    elif lon + mitad > 180.0:
        lon = 180.0 - mitad

    lat_min = max(-90.0, lat - mitad)
    lat_max = min(90.0, lat + mitad)
    lon_min = max(-180.0, lon - mitad)
    lon_max = min(180.0, lon + mitad)
    return lat_min, lon_min, lat_max, lon_max


def _rgb_y_cobertura(imagen):
    """Extrae RGB y una máscara de píxeles con datos reales.

    Worldview puede devolver un PNG 200 con el fondo negro cuando no hay
    cobertura para la fecha. El canal alfa suele ser opaco, así que además de
    alfa se descartan los píxeles casi negros y las imágenes planas.
    """
    if imagen.mode in ("RGBA", "LA") or "transparency" in imagen.info:
        rgba = np.asarray(imagen.convert("RGBA"), dtype=np.uint8)
        alpha = rgba[..., 3]
        rgb = rgba[..., :3].copy()
        rgb[alpha < 8] = 0
        validos = alpha > 8
    else:
        rgb = np.asarray(imagen.convert("RGB"), dtype=np.uint8)
        validos = np.ones(rgb.shape[:2], dtype=bool)

    luma = (
        rgb[..., 0].astype(np.float32) * 0.299
        + rgb[..., 1].astype(np.float32) * 0.587
        + rgb[..., 2].astype(np.float32) * 0.114
    )
    validos &= luma > 6.0

    if luma.std() < 1.5 and (luma.mean() < 8.0 or luma.mean() > 250.0):
        validos[:] = False

    return rgb, validos, float(validos.mean())


def _descargar_satelite(fecha, capa, bbox, tamano=SAT_SIZE):
    """Descarga una imagen GIBS y falla con ``SateliteSinCobertura`` si está vacía."""
    bbox_texto = ",".join(f"{valor:.4f}" for valor in bbox)
    tamano = max(256, min(2048, int(tamano)))
    parametros = {
        "REQUEST": "GetSnapshot",
        "LAYERS": capa,
        "CRS": "EPSG:4326",
        "TIME": fecha.isoformat(),
        "BBOX": bbox_texto,
        "WIDTH": tamano,
        "HEIGHT": tamano,
        "FORMAT": "image/png",
    }

    try:
        respuesta = requests.get(
            GIBS_SNAPSHOT_URL,
            params=parametros,
            headers={"User-Agent": USER_AGENT, "Accept": "image/png,image/*"},
            timeout=SAT_TIMEOUT,
        )
    except requests.Timeout:
        raise NasaError("Tiempo de espera agotado al descargar la imagen satelital.") from None
    except requests.ConnectionError:
        raise NasaError("Sin conexión a Internet para descargar la imagen satelital.") from None
    except requests.RequestException:
        raise NasaError("No se pudo descargar la imagen satelital.") from None

    if respuesta.status_code == 429:
        raise NasaError("Límite de peticiones satelitales alcanzado. Espera unos minutos.")
    if respuesta.status_code >= 500:
        raise NasaError("El servidor satelital no está disponible. Inténtalo más tarde.")
    if respuesta.status_code >= 400:
        raise SateliteSinCobertura("La fecha o la capa satelital no está disponible.")

    tipo = respuesta.headers.get("Content-Type", "").lower()
    if "image" not in tipo:
        raise SateliteSinCobertura("La respuesta satelital no contiene una imagen.")
    if len(respuesta.content) > MAX_IMAGEN_BYTES:
        raise NasaError("La imagen satelital recibida es demasiado grande.")

    try:
        imagen = Image.open(io.BytesIO(respuesta.content))
        imagen.load()
        imagen = ImageOps.exif_transpose(imagen)
    except Exception:
        raise SateliteSinCobertura("No se pudo interpretar la imagen satelital.") from None

    if min(imagen.size) < 64:
        raise SateliteSinCobertura("La imagen satelital recibida es demasiado pequeña.")

    rgb, validos, cobertura = _rgb_y_cobertura(imagen)
    if cobertura < SAT_MIN_COBERTURA:
        raise SateliteSinCobertura("Sin cobertura satelital utilizable para esa fecha.")

    return rgb, cobertura


def _imagen_analisis(datos):
    """Convierte una matriz o imagen a RGB 256x256 para la comparación."""
    if isinstance(datos, Image.Image):
        imagen = datos.convert("RGB")
    else:
        matriz = np.asarray(datos)
        if matriz.ndim == 2:
            matriz = np.repeat(matriz[..., None], 3, axis=2)
        if matriz.ndim != 3:
            raise NasaError("La imagen satelital no tiene un formato válido.")
        if matriz.shape[2] == 4:
            matriz = matriz[..., :3]
        elif matriz.shape[2] < 3:
            raise NasaError("La imagen satelital no tiene tres canales de color.")
        matriz = np.clip(matriz, 0, 255).astype(np.uint8)
        imagen = Image.fromarray(matriz[..., :3], "RGB")

    return imagen.resize((SAT_ANALYSIS_SIZE, SAT_ANALYSIS_SIZE), Image.Resampling.LANCZOS)


def _png_satelite(imagen):
    """Serializa una imagen RGB a PNG para transportarla al hilo de UI."""
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def comparar_imagenes_satelitales(antes, despues):
    """Compara dos matrices satelitales y estima el cambio territorial.

    Acepta matrices NumPy o imágenes Pillow con cualquier resolución; ambas se
    normalizan a 256x256. Devuelve un diccionario serializable con el porcentaje
    de píxeles alterados, la severidad ponderada, la cobertura válida y la
    cobertura de nubes. La heurística combina diferencia RGB, pérdida de verdor
    y oscurecimiento; los píxeles brillantes y poco saturados se excluyen por
    considerarse nubes.
    """
    imagen_antes = _imagen_analisis(antes)
    imagen_despues = _imagen_analisis(despues)
    a = np.asarray(imagen_antes, dtype=np.float32)
    b = np.asarray(imagen_despues, dtype=np.float32)

    luma_a = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    luma_b = b[..., 0] * 0.299 + b[..., 1] * 0.587 + b[..., 2] * 0.114

    def nublado(rgb):
        brillo = rgb.min(axis=2)
        saturacion = rgb.max(axis=2) - brillo
        return (brillo > 200.0) & (saturacion <= 25.0)

    nubes = nublado(a) | nublado(b)
    validos = (luma_a > 6.0) & (luma_b > 6.0) & ~nubes
    cobertura = float(validos.mean())
    cobertura_nubes = float(nubes.mean())
    if cobertura < SAT_MIN_COBERTURA:
        raise NasaError("Las imágenes satelitales no tienen cobertura suficiente para comparar.")

    diferencia = np.abs(a - b).mean(axis=2)
    verde_a = a[..., 1] - (a[..., 0] + a[..., 2]) / 2.0
    verde_b = b[..., 1] - (b[..., 0] + b[..., 2]) / 2.0
    perdida_verdor = np.maximum(0.0, verde_a - verde_b)
    oscurecimiento = np.maximum(0.0, luma_a - luma_b)
    cambio = np.maximum.reduce(
        (diferencia, perdida_verdor * 0.8, oscurecimiento * 0.6)
    )

    alterados = (cambio >= SAT_THRESHOLD) & validos
    pixeles_validos = int(validos.sum())
    pixeles_alterados = int(alterados.sum())
    cambio_pct = 100.0 * pixeles_alterados / max(1, pixeles_validos)
    intensidad = float(cambio[alterados].mean() / 255.0 * 100.0) if pixeles_alterados else 0.0
    severidad = cambio_pct * (0.55 + 0.45 * min(1.0, intensidad / 100.0))

    return {
        "cambio_pct": round(cambio_pct, 1),
        "severidad": round(severidad, 1),
        "cobertura": round(cobertura, 3),
        "cobertura_nubes": round(cobertura_nubes, 3),
        "pixeles_alterados": pixeles_alterados,
        "pixeles_validos": pixeles_validos,
        "metodo": "diferencia_rgb+perdida_verdor+oscurecimiento",
    }


def _limpiar_html(valor):
    """Convierte un fragmento HTML de APOD en texto plano."""
    texto = re.sub(r"<script\b.*?</script>", " ", valor or "", flags=re.I | re.S)
    texto = re.sub(r"<style\b.*?</style>", " ", texto, flags=re.I | re.S)
    texto = re.sub(r"<br\s*/?>", " ", texto, flags=re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html_lib.unescape(texto)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    return " ".join(texto.split())


def _youtube_id(url):
    """Extrae el ID de un enlace embed de YouTube, si existe."""
    match = re.search(
        r"(?:youtube(?:-nocookie)?\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)"
        r"([A-Za-z0-9_-]{6,})",
        url or "",
        re.I,
    )
    return match.group(1) if match else ""


def _get(url, params=None, *, timeout=TIMEOUT, intentos=2):
    """GET con timeout y un reintento para fallos transitorios de NASA.

    Los 4xx se devuelven como error inmediato; los 5xx, timeouts y cortes de
    conexión se reintentan una vez. Nunca se incluye la URL ni la API Key en
    el mensaje que llega a la interfaz.
    """
    ultimo_error = "No se pudo conectar con NASA."
    for intento in range(max(1, int(intentos))):
        try:
            respuesta = requests.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=timeout,
            )

            if respuesta.status_code == 429:
                raise NasaError("Límite de peticiones de NASA alcanzado. Espera unos minutos.")
            if respuesta.status_code in (401, 403):
                raise NasaError("La clave de NASA no es válida o no tiene permisos.")
            if respuesta.status_code >= 500:
                ultimo_error = "NASA no está disponible en este momento. Reintenta en un momento."
            elif respuesta.status_code >= 400:
                raise NasaError("NASA rechazó la solicitud. Revisa la clave o inténtalo más tarde.")
            else:
                return respuesta
        except NasaError:
            raise
        except requests.Timeout:
            ultimo_error = "Tiempo de espera agotado al conectar con NASA."
        except requests.ConnectionError:
            ultimo_error = "Sin conexión a Internet."
        except requests.RequestException:
            ultimo_error = "No se pudo conectar con NASA."

        if intento + 1 < max(1, int(intentos)):
            time.sleep(0.8)

    raise NasaError(ultimo_error)


def _get_json(url, params=None, *, timeout=TIMEOUT, intentos=2):
    """Descarga y valida una respuesta JSON de NASA."""
    respuesta = _get(url, params, timeout=timeout, intentos=intentos)
    try:
        return respuesta.json()
    except ValueError:
        raise NasaError("NASA devolvió una respuesta inesperada.") from None


def _coord(punto):
    """Convierte un punto EONET ``[lon, lat]`` en ``(lat, lon)``."""
    if not isinstance(punto, (list, tuple)) or len(punto) < 2:
        return None
    lon = _f(punto[0])
    lat = _f(punto[1])
    if lon is None or lat is None:
        return None
    return lat, lon


def _promedio(puntos):
    """Calcula un centro aproximado para líneas y anillos de EONET."""
    validos = []
    for punto in puntos or []:
        coord = _coord(punto)
        if coord is not None:
            validos.append(coord)
    if not validos:
        return None
    lat = sum(c[0] for c in validos) / len(validos)
    lon = sum(c[1] for c in validos) / len(validos)
    return lat, lon


def _punto_poligono(coordenadas):
    """Obtiene el centro del anillo exterior de un polígono EONET."""
    if not coordenadas:
        return None
    primero = coordenadas[0]
    # Formato habitual: [[[lon, lat], ...]]. Algunas fuentes entregan
    # directamente [[lon, lat], ...]; se aceptan ambos.
    if primero and isinstance(primero[0], (int, float)):
        return _promedio(coordenadas)
    return _promedio(primero)


def _punto_evento(geometrias):
    """Normaliza la última geometría de un evento EONET a ``(lat, lon)``."""
    if not geometrias:
        return None

    geometria = geometrias[-1]
    tipo = geometria.get("type")
    coordenadas = geometria.get("coordinates")

    if tipo == "Point":
        return _coord(coordenadas)
    if tipo in ("LineString", "MultiPoint"):
        return _promedio(coordenadas)
    if tipo == "Polygon":
        return _punto_poligono(coordenadas)
    if tipo == "MultiPolygon":
        poligonos = [p for p in (coordenadas or []) if p]
        if not poligonos:
            return None
        mayor = max(poligonos, key=lambda p: len(p[0]) if p and p[0] else 0)
        return _punto_poligono(mayor)
    return None


class NasaService:
    """Consultas NASA asíncronas con una cola de resultados."""

    def __init__(self):
        self.api_key = (os.getenv("NASA_API_KEY") or "").strip()
        self._cola = queue.Queue()
        self._en_vuelo = set()
        self._cerrado = False
        self._ejecutor_satelite = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="nasa-satelite"
        )

    @property
    def tiene_clave(self):
        return bool(self.api_key)

    def solicitar(self, tipo, **kwargs):
        """Lanza una consulta en un hilo daemon.

        Devuelve ``True`` si el hilo arrancó y ``False`` si ya había una
        consulta igual en curso, si el servicio se cerró o si falta la clave.
        Las consultas ``satelite`` se pueden solapar para que un cambio de
        selección no tenga que esperar a una descarga anterior.
        """
        if self._cerrado or (tipo in self._en_vuelo and tipo != "satelite"):
            return False

        if tipo in ("neows", "apod") and not self.tiene_clave:
            self._cola.put((tipo, None, "Falta NASA_API_KEY en tierra/.env."))
            return False

        # Las comparaciones satelitales pueden solaparse: si Jefe cambia de
        # evento, la nueva descarga no espera a que termine la anterior. La UI
        # cachea cada resultado por clave y solo muestra la selección actual.
        if tipo == "satelite":
            try:
                self._ejecutor_satelite.submit(self._ejecutar, tipo, kwargs)
            except RuntimeError:
                return False
            return True

        self._en_vuelo.add(tipo)
        hilo = threading.Thread(
            target=self._ejecutar,
            args=(tipo, kwargs),
            daemon=True,
            name=f"nasa-{tipo}",
        )
        hilo.start()
        return True

    def poll(self):
        """Entrega los resultados disponibles sin bloquear el hilo principal."""
        while True:
            try:
                tipo, datos, error = self._cola.get_nowait()
            except queue.Empty:
                return
            self._en_vuelo.discard(tipo)
            yield tipo, datos, error

    def cerrar(self):
        """Cierra el servicio y cancela las descargas satelitales pendientes."""
        self._cerrado = True
        self._ejecutor_satelite.shutdown(wait=False, cancel_futures=True)

    def _ejecutar(self, tipo, kwargs):
        try:
            if tipo == "eonet":
                datos = self._fetch_eonet(**kwargs)
            elif tipo == "neows":
                datos = self._fetch_neows(**kwargs)
            elif tipo == "apod":
                datos = self._fetch_apod(**kwargs)
            elif tipo == "apod_imagen":
                datos = self._fetch_imagen(**kwargs)
            elif tipo == "satelite":
                datos = self._fetch_satelite(**kwargs)
            else:
                raise NasaError("Tipo de consulta NASA desconocido.")
        except NasaError as exc:
            if tipo == "satelite":
                self._cola.put((tipo, {"clave": kwargs.get("clave", "")}, str(exc)))
            else:
                self._cola.put((tipo, None, str(exc)))
        except Exception:
            # No se propaga el detalle interno ni la clave a la interfaz.
            mensaje = "Error inesperado al consultar NASA."
            if tipo == "satelite":
                self._cola.put((tipo, {"clave": kwargs.get("clave", "")}, mensaje))
            else:
                self._cola.put((tipo, None, mensaje))
        else:
            self._cola.put((tipo, datos, None))

    def _fetch_eonet(self, modo="activos", dias=None):
        """Eventos naturales en modo activo o histórico.

        ``activos`` consulta ``status=open`` y los últimos 7 días. ``historicos``
        usa ``status=all`` y 30 días para incluir eventos ya cerrados. El
        resultado es una ``EventosEonet`` (subclase de lista) con el modo y el
        rango usados, para que la interfaz pueda descartar respuestas viejas al
        alternar con la tecla V.
        """
        modo = "historicos" if str(modo).lower().startswith("hist") else "activos"
        config = EONET_MODOS[modo]
        dias = _i(config["dias"] if dias is None else dias, config["dias"])
        status = config["status"]

        datos = _get_json(EONET_URL, {"status": status, "days": dias})
        eventos = []

        for evento in datos.get("events", []) or []:
            geometrias = evento.get("geometry") or []
            punto = _punto_evento(geometrias)
            if punto is None:
                continue

            lat, lon = punto
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue

            categorias = evento.get("categories") or []
            categoria = categorias[0] if categorias else {}
            ultima = geometrias[-1] if geometrias else {}
            cerrado = bool(evento.get("closed"))

            eventos.append({
                "id": str(evento.get("id", "")),
                "titulo": _texto(evento.get("title"), "Evento sin título"),
                "categoria": _texto(categoria.get("id"), "otros"),
                "categoria_titulo": _texto(categoria.get("title"), "Otros"),
                "lat": float(lat),
                "lon": float(lon),
                "fecha": _fecha_corta(ultima.get("date")),
                "fecha_inicio": (
                    _fecha_corta(geometrias[0].get("date"))
                    if geometrias else ""
                ),
                "link": _texto(evento.get("link")),
                "magnitud": ultima.get("magnitudeValue"),
                "unidad": _texto(ultima.get("magnitudeUnit")),
                "cerrado": cerrado,
                "estado": "cerrado" if cerrado else "activo",
                "modo": modo,
            })

        return EventosEonet(eventos, modo, dias, status)

    def _fetch_satelite(self, evento=None, clave=None, recorte=SAT_RECORTE):
        """Busca un par Antes/Después en GIBS y compara el cambio territorial.

        Se prueban capas MODIS/VIIRS hasta encontrar una que tenga cobertura
        en las dos fechas. La misma capa se usa en ambas imágenes para evitar
        comparar sensores distintos. El Antes usa ``fecha_inicio - 2 días``; el
        Después intenta ``fecha_fin + 1 día`` y, si no hay cobertura, la fecha
        exacta de cierre del evento. Si el evento es de hoy y GIBS aún no tiene
        su imagen, se devuelve un mensaje específico.

        ``recorte`` es el ancho geográfico en grados. La vista normal usa 2°;
        los niveles de 1° y 0.5° permiten acercarse sin cambiar de capa.
        """
        if not isinstance(evento, dict):
            raise NasaError("No hay un evento seleccionado para comparar imágenes.")

        lat = _f(evento.get("lat"))
        lon = _f(evento.get("lon"))
        if lat is None or lon is None:
            raise NasaError("El evento no tiene coordenadas para la comparación satelital.")
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise NasaError("Las coordenadas del evento no son válidas.")

        recorte = round(max(0.1, min(20.0, _f(recorte, SAT_RECORTE))), 2)
        antes, candidatos_despues = _fechas_satelite(evento)
        fecha_fin = _fecha_evento(evento)
        hoy = dt.date.today()
        bbox = _bbox_satelite(lat, lon, recorte)
        imagenes = {}

        for capa in SAT_CAPAS:
            try:
                llave_antes = (capa, antes)
                if llave_antes not in imagenes:
                    imagenes[llave_antes] = _descargar_satelite(antes, capa, bbox)
                rgb_antes, cobertura_antes = imagenes[llave_antes]
            except SateliteSinCobertura:
                continue

            for despues in candidatos_despues:
                try:
                    llave_despues = (capa, despues)
                    if llave_despues not in imagenes:
                        imagenes[llave_despues] = _descargar_satelite(despues, capa, bbox)
                    rgb_despues, cobertura_despues = imagenes[llave_despues]
                except SateliteSinCobertura:
                    continue

                try:
                    metricas = comparar_imagenes_satelitales(rgb_antes, rgb_despues)
                except NasaError:
                    continue
                imagen_antes = Image.fromarray(rgb_antes, "RGB")
                imagen_despues = Image.fromarray(rgb_despues, "RGB")
                miniatura_antes = imagen_antes.resize(
                    (SAT_ANALYSIS_SIZE, SAT_ANALYSIS_SIZE),
                    Image.Resampling.LANCZOS,
                )
                miniatura_despues = imagen_despues.resize(
                    (SAT_ANALYSIS_SIZE, SAT_ANALYSIS_SIZE),
                    Image.Resampling.LANCZOS,
                )

                resultado = {
                    "clave": clave or "",
                    "evento_id": _texto(evento.get("id")),
                    "titulo": _texto(evento.get("titulo"), "Evento sin título"),
                    "lat": float(lat),
                    "lon": float(lon),
                    "bbox": tuple(round(valor, 4) for valor in bbox),
                    "recorte": recorte,
                    "tamano": SAT_SIZE,
                    "resolucion_m": round(111320.0 * recorte / SAT_SIZE, 1),
                    "antes_fecha": antes.isoformat(),
                    "despues_fecha": despues.isoformat(),
                    "capa": capa,
                    "cobertura_antes": round(cobertura_antes, 3),
                    "cobertura_despues": round(cobertura_despues, 3),
                    "antes_png": _png_satelite(miniatura_antes),
                    "despues_png": _png_satelite(miniatura_despues),
                    "antes_full_png": _png_satelite(imagen_antes),
                    "despues_full_png": _png_satelite(imagen_despues),
                }
                resultado.update(metricas)
                return resultado

        if fecha_fin == hoy:
            raise NasaError("Imagen de hoy aún no disponible en GIBS.")
        fechas = " / ".join(fecha.isoformat() for fecha in candidatos_despues)
        raise NasaError(
            f"Sin cobertura satelital para {antes.isoformat()} y {fechas}."
        )

    def _fetch_neows(self):
        """Asteroides cercanos de los próximos siete días (hoy incluido)."""
        hoy = dt.datetime.now(dt.timezone.utc).date()
        hasta = hoy + dt.timedelta(days=6)
        datos = _get_json(NEOWS_URL, {
            "start_date": hoy.isoformat(),
            "end_date": hasta.isoformat(),
            "api_key": self.api_key,
        })

        objetos = []
        for fecha, lista in (datos.get("near_earth_objects") or {}).items():
            for neo in lista or []:
                aproximacion = (neo.get("close_approach_data") or [{}])[0]
                distancia = aproximacion.get("miss_distance") or {}
                velocidad = aproximacion.get("relative_velocity") or {}
                diametro = (
                    (neo.get("estimated_diameter") or {}).get("kilometers") or {}
                )

                objetos.append({
                    "nombre": _texto(neo.get("name"), "Sin nombre"),
                    "fecha": _texto(aproximacion.get("close_approach_date_full")) or fecha,
                    "distancia_km": _f(distancia.get("kilometers")),
                    "distancia_ld": _f(distancia.get("lunar")),
                    "distancia_au": _f(distancia.get("astronomical")),
                    "velocidad_kms": _f(velocidad.get("kilometers_per_second")),
                    "diametro_min_km": _f(diametro.get("estimated_diameter_min")),
                    "diametro_max_km": _f(diametro.get("estimated_diameter_max")),
                    "peligroso": bool(neo.get("is_potentially_hazardous_asteroid")),
                    "url": _texto(neo.get("nasa_jpl_url")),
                })

        objetos.sort(
            key=lambda o: (
                o["distancia_km"] is None,
                o["distancia_km"] if o["distancia_km"] is not None else float("inf"),
            )
        )

        return {
            "total": _i(datos.get("element_count"), len(objetos)),
            "objetos": objetos[:5],
            "desde": hoy.isoformat(),
            "hasta": hasta.isoformat(),
        }

    def _fetch_apod(self):
        """Información de APOD; usa la web oficial si la API falla."""
        error_api = None
        try:
            datos = _get_json(
                APOD_URL,
                {"api_key": self.api_key, "thumbs": "true"},
                timeout=(3, 5),
                intentos=1,
            )
            return self._normalizar_apod(datos)
        except NasaError as exc:
            error_api = exc

        try:
            return self._fetch_apod_web()
        except NasaError:
            raise error_api from None

    def _normalizar_apod(self, datos):
        """Normaliza la respuesta JSON de APOD al formato de la interfaz."""
        if not isinstance(datos, dict) or "code" in datos:
            raise NasaError("APOD no está disponible en este momento.")

        media = _texto(datos.get("media_type")).lower()
        url = _texto(datos.get("url"))
        thumbnail = _texto(datos.get("thumbnail_url"))

        if media == "image":
            imagen_url = url
        elif media == "video":
            imagen_url = thumbnail
        else:
            imagen_url = thumbnail

        return {
            "titulo": _texto(datos.get("title"), "APOD"),
            "fecha": _texto(datos.get("date")),
            "explicacion": " ".join(_texto(datos.get("explanation")).split()),
            "media_type": media,
            "url": url,
            "imagen_url": imagen_url,
            "copyright": _texto(datos.get("copyright")),
            "origen": "api",
        }

    def _fetch_apod_web(self):
        """Lee APOD desde su página oficial cuando la API no responde."""
        try:
            respuesta = requests.get(
                APOD_WEB_URL,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                timeout=(6, 15),
            )
        except requests.Timeout:
            raise NasaError("Tiempo de espera agotado al conectar con APOD.")
        except requests.RequestException:
            raise NasaError("No se pudo conectar con APOD.")

        if respuesta.status_code >= 400:
            raise NasaError("APOD no está disponible en este momento.")

        texto = respuesta.content.decode("utf-8", errors="replace")
        articulo = re.search(
            r'<article[^>]*class="[^"]*smd-embed-post__article[^"]*"[^>]*>'
            r"(.*?)</article>",
            texto,
            re.I | re.S,
        )
        bloque = articulo.group(1) if articulo else texto

        imagen = ""
        figura = re.search(
            r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"',
            bloque,
            re.I | re.S,
        )
        if figura:
            imagen = html_lib.unescape(figura.group(1)).strip()

        if not imagen:
            suelta = re.search(
                r'<img[^>]+src="([^"]*(?:apod|/dam/)[^"]*)"',
                bloque,
                re.I,
            )
            if suelta:
                imagen = html_lib.unescape(suelta.group(1)).strip()

        video = ""
        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', bloque, re.I)
        if iframe:
            video = html_lib.unescape(iframe.group(1)).strip()

        titulo = ""
        for match in re.finditer(r"<h2[^>]*>(.*?)</h2>", bloque, re.I | re.S):
            candidato = _limpiar_html(match.group(1))
            if candidato and candidato.lower() not in ("suggested searches",):
                titulo = candidato
                break
        if not titulo:
            titulo = "APOD"

        explicacion = ""
        parrafo = re.search(
            r'<p[^>]*class="[^"]*media-detail-hero__description[^"]*"[^>]*>'
            r"(.*?)</p>",
            bloque,
            re.I | re.S,
        )
        if parrafo:
            explicacion = _limpiar_html(parrafo.group(1))
        else:
            suelto = re.search(
                r"<strong>\s*Explanation:\s*</strong>(.*?)(?:Tomorrow|</p>)",
                bloque,
                re.I | re.S,
            )
            if suelto:
                explicacion = _limpiar_html(suelto.group(1))

        explicacion = re.sub(r"^\s*Explanation:\s*", "", explicacion, flags=re.I)
        explicacion = re.split(
            r"Tomorrow'?s picture:", explicacion, maxsplit=1, flags=re.I
        )[0].strip()

        fecha = ""
        fecha_html = re.search(
            r"<th[^>]*>\s*Date\s*</th>\s*<td[^>]*>(.*?)</td>",
            bloque,
            re.I | re.S,
        )
        if fecha_html:
            fecha_texto = _limpiar_html(fecha_html.group(1))
            for formato in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    fecha = dt.datetime.strptime(fecha_texto, formato).date().isoformat()
                    break
                except ValueError:
                    continue
            if not fecha:
                fecha = fecha_texto

        credito = ""
        credito_html = re.search(
            r"Credit\s*&(?:amp;)?\s*Copyright.*?</th>\s*<td[^>]*>(.*?)</td>",
            bloque,
            re.I | re.S,
        )
        if credito_html:
            credito = _limpiar_html(credito_html.group(1))

        if imagen:
            media = "image"
            url = imagen
            imagen_url = imagen
        elif video:
            media = "video"
            url = video
            video_id = _youtube_id(video)
            imagen_url = (
                f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                if video_id else ""
            )
        else:
            raise NasaError("APOD devolvió una página sin imagen ni vídeo.")

        return {
            "titulo": titulo,
            "fecha": fecha,
            "explicacion": explicacion,
            "media_type": media,
            "url": url,
            "imagen_url": imagen_url,
            "copyright": credito,
            "origen": "web",
        }

    def _fetch_imagen(self, url=""):
        """Descarga y reduce la imagen APOD a un PNG pequeño para Pygame."""
        if not url:
            raise NasaError("APOD no incluye una imagen válida.")

        ultimo_error = "No se pudo descargar la imagen de APOD."
        for intento in range(2):
            try:
                with requests.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=(6, 20),
                    stream=True,
                ) as respuesta:
                    if respuesta.status_code >= 500:
                        ultimo_error = "El servidor de imágenes de NASA no responde."
                    elif respuesta.status_code >= 400:
                        raise NasaError("No se pudo descargar la imagen de APOD.")
                    else:
                        tipo = (respuesta.headers.get("Content-Type") or "").lower()
                        if tipo and not tipo.startswith("image/"):
                            raise NasaError("La URL de APOD no es una imagen.")

                        datos = bytearray()
                        for bloque in respuesta.iter_content(64 * 1024):
                            if not bloque:
                                continue
                            datos.extend(bloque)
                            if len(datos) > MAX_IMAGEN_BYTES:
                                raise NasaError("La imagen de APOD es demasiado grande.")

                        if not datos:
                            raise NasaError("La imagen de APOD llegó vacía.")

                        try:
                            with Image.open(io.BytesIO(bytes(datos))) as original:
                                imagen = ImageOps.exif_transpose(original).convert("RGB")
                                imagen = ImageOps.fit(
                                    imagen,
                                    THUMB_SIZE,
                                    method=Image.Resampling.LANCZOS,
                                )
                                salida = io.BytesIO()
                                imagen.save(salida, format="PNG", optimize=True)
                                return {"url": url, "png": salida.getvalue()}
                        except (OSError, ValueError, Image.DecompressionBombError):
                            raise NasaError("No se pudo decodificar la imagen de APOD.")
            except NasaError:
                raise
            except requests.Timeout:
                ultimo_error = "Tiempo de espera agotado al descargar APOD."
            except requests.RequestException:
                ultimo_error = "No se pudo descargar la imagen de APOD."

            if intento == 0:
                time.sleep(0.6)

        raise NasaError(ultimo_error)


# ---------------------------------------------------------------------------
# Seguimiento orbital: descarga de TLE, propagación y muestreo en segundo plano
# ---------------------------------------------------------------------------


def _ahora_utc():
    return dt.datetime.now(dt.timezone.utc)


def _normalizar_instante(cuando=None):
    """Devuelve un ``datetime`` UTC; las fechas ingenuas se asumen UTC."""
    if cuando is None:
        return _ahora_utc()
    if cuando.tzinfo is None:
        return cuando.replace(tzinfo=dt.timezone.utc)
    return cuando.astimezone(dt.timezone.utc)


def _julian_date(cuando):
    """Fecha juliana UTC a partir de un ``datetime`` con zona horaria."""
    return 2440587.5 + cuando.timestamp() / 86400.0


def _gmst(jd):
    """Tiempo sidéreo medio de Greenwich en radianes (aprox. UT1≈UTC)."""
    siglos = (jd - 2451545.0) / 36525.0
    grados = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * siglos * siglos
        - (siglos ** 3) / 38710000.0
    )
    return math.radians(grados % 360.0)


def _eci_a_geografica(x, y, z, jd):
    """Convierte una posición inercial (km) a latitud/longitud/altitud WGS84."""
    giro = _gmst(jd)
    cos_giro = math.cos(giro)
    sin_giro = math.sin(giro)
    x_ecef = cos_giro * x + sin_giro * y
    y_ecef = -sin_giro * x + cos_giro * y
    z_ecef = z

    lon = math.degrees(math.atan2(y_ecef, x_ecef))
    radio_ecuatorial = math.hypot(x_ecef, y_ecef)
    e2 = EXCENTRICIDAD_TIERRA
    lat = math.atan2(z_ecef, radio_ecuatorial * (1.0 - e2))
    altitud = 0.0

    for _ in range(6):
        sin_lat = math.sin(lat)
        cos_lat = math.cos(lat)
        normal = RADIO_ECUATORIAL_KM / math.sqrt(
            1.0 - e2 * sin_lat * sin_lat
        )
        if abs(cos_lat) > 1e-8:
            altitud = radio_ecuatorial / cos_lat - normal
        else:
            altitud = abs(z_ecef) - normal * (1.0 - e2)
        nueva = math.atan2(
            z_ecef,
            radio_ecuatorial * (1.0 - e2 * normal / (normal + altitud)),
        )
        if abs(nueva - lat) < 1e-12:
            lat = nueva
            break
        lat = nueva

    return {
        "lat": math.degrees(lat),
        "lon": lon,
        "altitud_km": altitud,
        "radio_km": math.sqrt(x * x + y * y + z * z),
    }


def _bloques_tle(texto):
    """Extrae ``(nombre, línea 1, línea 2)`` de una respuesta TLE de Celestrak."""
    lineas = [line.strip("\ufeff\r\n") for line in (texto or "").splitlines()]
    bloques = []
    for indice in range(len(lineas) - 1):
        linea1 = lineas[indice]
        linea2 = lineas[indice + 1]
        if not (linea1.startswith("1 ") and linea2.startswith("2 ")):
            continue
        nombre = ""
        if indice > 0:
            anterior = lineas[indice - 1].strip()
            if anterior and not anterior.startswith(("1 ", "2 ")):
                nombre = anterior
        bloques.append((nombre, linea1, linea2))
    return bloques


def _fecha_epoca_tle(linea1):
    """Época del TLE (año de dos dígitos + día fraccional del año) en UTC."""
    anio_corto = int(linea1[18:20])
    dia = float(linea1[20:32])
    anio = 2000 + anio_corto if anio_corto < 57 else 1900 + anio_corto
    return dt.datetime(anio, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(
        days=dia - 1.0
    )


def _elementos_tle(linea1, linea2):
    """Elementos orbitales medios del TLE en unidades internas (rad, km)."""
    if not (linea1.startswith("1 ") and linea2.startswith("2 ")):
        raise ValueError("TLE no válido")
    movimiento = float(linea2[52:63])
    excentricidad = float("0." + linea2[26:33].strip())
    inclinacion = float(linea2[8:16])
    if movimiento <= 0.0 or not (0.0 <= excentricidad < 1.0):
        raise ValueError("Elementos orbitales fuera de rango")

    return {
        "epoca": _fecha_epoca_tle(linea1),
        "inclinacion": math.radians(inclinacion),
        "inclinacion_deg": inclinacion,
        "raan": math.radians(float(linea2[17:25])),
        "excentricidad": excentricidad,
        "arg_perigeo": math.radians(float(linea2[34:42])),
        "anomalia_media": math.radians(float(linea2[43:51])),
        "movimiento_medio": movimiento,
        "periodo_min": 1440.0 / movimiento,
    }


def _celestrak_get(parametros):
    """GET de texto plano contra la API GP de Celestrak."""
    try:
        respuesta = requests.get(
            CELESTRAK_GP_URL,
            params=parametros,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain,application/json",
            },
            timeout=(6, 20),
        )
    except requests.Timeout:
        raise NasaError("Tiempo de espera agotado al consultar Celestrak.") from None
    except requests.ConnectionError:
        raise NasaError("Sin conexión a Internet para consultar Celestrak.") from None
    except requests.RequestException:
        raise NasaError("No se pudo consultar Celestrak.") from None

    if respuesta.status_code == 429:
        raise NasaError("Celestrak limitó las peticiones. Se reintentará en breve.")
    if respuesta.status_code in (401, 403):
        raise NasaError("Celestrak bloqueó la consulta de TLE.")
    if respuesta.status_code >= 500:
        raise NasaError("El servidor de Celestrak no está disponible.")
    if respuesta.status_code >= 400:
        raise NasaError("Celestrak rechazó la consulta de TLE.")

    texto = (respuesta.text or "").strip()
    if not texto:
        raise NasaError("Celestrak devolvió una respuesta vacía.")
    if texto.lstrip().startswith("<"):
        raise NasaError("Celestrak devolvió una página en lugar de TLE.")
    return texto


def _registro_tle(config, nombre_oficial, linea1, linea2):
    """Construye el satélite listo para propagar a partir de su TLE oficial."""
    elementos = _elementos_tle(linea1, linea2)
    return {
        "catnr": int(config["catnr"]),
        "nombre": config["nombre"],
        "objeto": nombre_oficial or config["nombre"],
        "grupo": config["grupo"],
        "color": tuple(config["color"]),
        "linea1": linea1,
        "linea2": linea2,
        "elementos": elementos,
        "periodo_min": elementos["periodo_min"],
        "inclinacion_deg": elementos["inclinacion_deg"],
    }


def descargar_tles(satelites=SATELITES_NASA):
    """Descarga los TLE oficiales de Celestrak para los satélites pedidos.

    Primero consulta los grupos ``stations``, ``science``, ``resource`` y
    ``weather`` (cuatro peticiones pequeñas) y luego recurre a ``CATNR`` solo
    para los que falten. La pausa entre peticiones evita el límite de 1 req/s.
    """
    objetivos = {int(satelite["catnr"]): satelite for satelite in satelites}
    encontrados = {}
    errores = []

    for grupo in CELESTRAK_GRUPOS:
        faltantes = [catnr for catnr in objetivos if catnr not in encontrados]
        if not faltantes:
            break
        try:
            texto = _celestrak_get({"GROUP": grupo, "FORMAT": "tle"})
        except NasaError as exc:
            errores.append(str(exc))
        else:
            for nombre, linea1, linea2 in _bloques_tle(texto):
                catnr = _i(linea1[2:7])
                if catnr not in objetivos or catnr in encontrados:
                    continue
                try:
                    encontrados[catnr] = _registro_tle(
                        objetivos[catnr], nombre, linea1, linea2
                    )
                except (ValueError, IndexError):
                    continue
        time.sleep(CELESTRAK_PAUSA)

    for catnr in [c for c in objetivos if c not in encontrados]:
        try:
            texto = _celestrak_get({"CATNR": catnr, "FORMAT": "tle"})
        except NasaError as exc:
            errores.append(str(exc))
        else:
            for nombre, linea1, linea2 in _bloques_tle(texto):
                if _i(linea1[2:7]) != catnr:
                    continue
                try:
                    encontrados[catnr] = _registro_tle(
                        objetivos[catnr], nombre, linea1, linea2
                    )
                except (ValueError, IndexError):
                    continue
                break
        time.sleep(CELESTRAK_PAUSA)

    if not encontrados:
        mensaje = errores[-1] if errores else "Celestrak no devolvió TLE utilizables."
        raise NasaError(mensaje)

    return [encontrados[catnr] for catnr in objetivos if catnr in encontrados]


def _elementos_actuales(tle, cuando):
    """Elementos osculadores aproximados con precesión secular J2.

    El movimiento medio del TLE es Kozai; se convierte a Brouwer antes de
    propagar, igual que hace la inicialización de SGP4. Sin esa corrección el
    error de fase crece decenas de kilómetros en pocas horas.
    """
    elementos = tle["elementos"]
    segundos = (cuando - elementos["epoca"]).total_seconds()
    n_kozai = elementos["movimiento_medio"] * 2.0 * math.pi / 86400.0
    excentricidad = elementos["excentricidad"]
    inclinacion = elementos["inclinacion"]

    excentricidad2 = excentricidad * excentricidad
    uno_menos_e2 = 1.0 - excentricidad2
    raiz = math.sqrt(max(0.0, uno_menos_e2))
    cos_i = math.cos(inclinacion)
    cos_i2 = cos_i * cos_i

    # Kozai -> Brouwer (initl de SGP4).
    semieje_kozai = (MU_TIERRA / (n_kozai * n_kozai)) ** (1.0 / 3.0)
    semieje_er = semieje_kozai / RADIO_ECUATORIAL_KM
    d1 = (
        0.75 * J2_TIERRA * (3.0 * cos_i2 - 1.0)
        / max(1e-12, raiz * uno_menos_e2)
    )
    delta = d1 / (semieje_er * semieje_er)
    adelgazado = semieje_er * (
        1.0 - delta * delta - delta * (1.0 / 3.0 + 134.0 * delta * delta / 81.0)
    )
    delta = d1 / max(1e-12, adelgazado * adelgazado)
    n0 = n_kozai / (1.0 + delta)
    semieje = (MU_TIERRA / (n0 * n0)) ** (1.0 / 3.0)

    parametro = semieje * uno_menos_e2
    factor = J2_TIERRA * (RADIO_ECUATORIAL_KM / parametro) ** 2

    raan = elementos["raan"] - 1.5 * n0 * factor * cos_i * segundos
    arg_perigeo = (
        elementos["arg_perigeo"]
        + 0.75 * n0 * factor * (5.0 * cos_i2 - 1.0) * segundos
    )
    anomalia = (
        elementos["anomalia_media"]
        + n0 * segundos
        * (1.0 + 0.75 * factor * raiz * (3.0 * cos_i2 - 1.0))
    )

    return {
        "semieje": semieje,
        "excentricidad": excentricidad,
        "inclinacion": inclinacion,
        "raan": raan % (2.0 * math.pi),
        "arg_perigeo": arg_perigeo % (2.0 * math.pi),
        "anomalia_media": anomalia % (2.0 * math.pi),
    }


def _resolver_kepler(anomalia_media, excentricidad):
    """Resuelve E - e·sin(E) = M con Newton-Raphson."""
    anomalia_excentrica = anomalia_media if excentricidad < 0.8 else math.pi
    for _ in range(10):
        delta = (
            anomalia_excentrica
            - excentricidad * math.sin(anomalia_excentrica)
            - anomalia_media
        ) / (1.0 - excentricidad * math.cos(anomalia_excentrica))
        anomalia_excentrica -= delta
        if abs(delta) < 1e-11:
            break
    return anomalia_excentrica


def _perifocal_a_eci(x_perifocal, y_perifocal, inclinacion, raan, arg_perigeo):
    """Rota el plano orbital a coordenadas inerciales (km)."""
    cos_w, sin_w = math.cos(arg_perigeo), math.sin(arg_perigeo)
    cos_o, sin_o = math.cos(raan), math.sin(raan)
    cos_i, sin_i = math.cos(inclinacion), math.sin(inclinacion)

    x = (cos_o * cos_w - sin_o * sin_w * cos_i) * x_perifocal + (
        -cos_o * sin_w - sin_o * cos_w * cos_i
    ) * y_perifocal
    y = (sin_o * cos_w + cos_o * sin_w * cos_i) * x_perifocal + (
        -sin_o * sin_w + cos_o * cos_w * cos_i
    ) * y_perifocal
    z = (sin_w * sin_i) * x_perifocal + (cos_w * sin_i) * y_perifocal
    return x, y, z


def _estado_sgp4(satrec, cuando):
    """Propaga con SGP4 si la librería opcional ``sgp4`` está instalada."""
    instante = cuando.astimezone(dt.timezone.utc)
    jd, fraccion = _jday(
        instante.year,
        instante.month,
        instante.day,
        instante.hour,
        instante.minute,
        instante.second + instante.microsecond * 1e-6,
    )
    error, posicion, velocidad = satrec.sgp4(jd, fraccion)
    if error != 0:
        raise ValueError(f"SGP4 error {error}")

    x, y, z = (float(valor) for valor in posicion)
    estado = _eci_a_geografica(x, y, z, jd + fraccion)
    estado["velocidad_kms"] = math.sqrt(
        sum(float(componente) ** 2 for componente in velocidad)
    )
    return estado


def _estado_kepleriano(tle, cuando):
    """Propagador simplificado (Kepler + J2) cuando no hay ``sgp4``."""
    elementos = _elementos_actuales(tle, cuando)
    excentricidad = elementos["excentricidad"]
    anomalia_excentrica = _resolver_kepler(
        elementos["anomalia_media"], excentricidad
    )
    anomalia_verdadera = math.atan2(
        math.sqrt(max(0.0, 1.0 - excentricidad * excentricidad))
        * math.sin(anomalia_excentrica),
        math.cos(anomalia_excentrica) - excentricidad,
    )
    radio = elementos["semieje"] * (
        1.0 - excentricidad * math.cos(anomalia_excentrica)
    )
    x_perifocal = radio * math.cos(anomalia_verdadera)
    y_perifocal = radio * math.sin(anomalia_verdadera)
    x, y, z = _perifocal_a_eci(
        x_perifocal,
        y_perifocal,
        elementos["inclinacion"],
        elementos["raan"],
        elementos["arg_perigeo"],
    )

    estado = _eci_a_geografica(x, y, z, _julian_date(cuando))
    estado["velocidad_kms"] = math.sqrt(
        MU_TIERRA * max(0.0, 2.0 / radio - 1.0 / elementos["semieje"])
    )
    return estado


def propagar_satelite(tle, cuando=None):
    """Posición geográfica y velocidad de un TLE para un instante UTC.

    Usa SGP4 si ``sgp4`` está disponible; si no, el propagador Kepler + J2
    incluido en este módulo. Devuelve ``lat``, ``lon``, ``altitud_km``,
    ``velocidad_kms`` y ``radio_km``.
    """
    cuando = _normalizar_instante(cuando)
    satrec = tle.get("_satrec")
    if satrec is None and _Satrec is not None:
        try:
            satrec = _Satrec.twoline2rv(tle["linea1"], tle["linea2"])
            tle["_satrec"] = satrec
        except Exception:
            satrec = None

    if satrec is not None:
        try:
            return _estado_sgp4(satrec, cuando)
        except Exception:
            pass

    return _estado_kepleriano(tle, cuando)


def orbita_satelite(tle, cuando=None, puntos=96):
    """Anillo orbital instantáneo como ``(lat, lon, altitud_km)``."""
    cuando = _normalizar_instante(cuando)
    elementos = _elementos_actuales(tle, cuando)
    excentricidad = elementos["excentricidad"]
    if excentricidad >= 1.0:
        return []

    jd = _julian_date(cuando)
    pasos = max(24, int(puntos))
    anillo = []
    for paso in range(pasos):
        angulo = 2.0 * math.pi * paso / pasos
        radio = (
            elementos["semieje"]
            * (1.0 - excentricidad * excentricidad)
            / (1.0 + excentricidad * math.cos(angulo))
        )
        x, y, z = _perifocal_a_eci(
            radio * math.cos(angulo),
            radio * math.sin(angulo),
            elementos["inclinacion"],
            elementos["raan"],
            elementos["arg_perigeo"],
        )
        estado = _eci_a_geografica(x, y, z, jd)
        anillo.append((estado["lat"], estado["lon"], estado["altitud_km"]))
    return anillo


class RastreadorSatelites:
    """Descarga TLE y propaga órbitas en un hilo, con interpolación para la UI.

    El hilo calcula dos muestras separadas por ``intervalo`` segundos. La
    interfaz pide ``estados()`` y recibe la posición interpolada de cada
    satélite, de modo que el globo se mueve suave a 60 FPS sin hacer cálculos
    orbitales en el hilo de render.
    """

    def __init__(self, satelites=SATELITES_NASA, intervalo=0.4, ttl=TLE_TTL):
        self._config = tuple(satelites)
        self._intervalo = max(0.15, float(intervalo))
        self._ttl = max(60.0, float(ttl))
        self._lock = threading.Lock()
        self._hilo = None
        self._hilo_tle = None
        self._parado = threading.Event()
        self._tles = []
        self._ts_tle = 0.0
        self._muestreo = None
        self._error = None
        self._cargando = False
        self._reintento_ts = 0.0
        self._cargar_cache_tle()

    @property
    def cargando(self):
        return self._cargando

    @property
    def error(self):
        return self._error

    @property
    def total(self):
        return len(self._tles)

    @property
    def edad_tle(self):
        if not self._ts_tle:
            return None
        return max(0.0, time.time() - self._ts_tle)

    @property
    def sgp4_disponible(self):
        return _Satrec is not None

    @property
    def iniciado(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self):
        """Arranca el muestreo y la descarga TLE en hilos independientes."""
        if self.iniciado:
            return
        self._parado.clear()
        self._hilo = threading.Thread(
            target=self._bucle, daemon=True, name="tierra-satelites"
        )
        self._hilo_tle = threading.Thread(
            target=self._bucle_tle, daemon=True, name="tierra-satelites-tle"
        )
        self._hilo.start()
        self._hilo_tle.start()

    def cerrar(self):
        self._parado.set()

    def estados(self, cuando=None):
        """Posiciones interpoladas en el instante pedido (por defecto, ahora)."""
        with self._lock:
            muestreo = self._muestreo
        if not muestreo:
            return []

        ahora = time.time() if cuando is None else float(cuando)
        t0 = muestreo["t0"]
        t1 = muestreo["t1"]
        if ahora <= t0:
            return [dict(estado) for estado in muestreo["a"]]
        if ahora >= t1:
            return [dict(estado) for estado in muestreo["b"]]

        fraccion = (ahora - t0) / max(1e-6, t1 - t0)
        siguientes = {
            estado["catnr"]: estado for estado in muestreo["b"]
        }
        salida = []
        for previo in muestreo["a"]:
            siguiente = siguientes.get(previo["catnr"])
            if siguiente is not None:
                salida.append(self._interpolar(previo, siguiente, fraccion))
        return salida

    def orbita(self, catnr, puntos=96):
        """Anillo orbital del satélite indicado, o ``[]`` si no hay TLE."""
        with self._lock:
            tles = tuple(self._tles)
        for tle in tles:
            if tle["catnr"] == catnr:
                try:
                    return orbita_satelite(tle, puntos=puntos)
                except Exception:
                    return []
        return []

    @staticmethod
    def _interpolar(previo, siguiente, fraccion):
        estado = dict(previo)
        estado["lat"] = previo["lat"] + (siguiente["lat"] - previo["lat"]) * fraccion
        delta_lon = (siguiente["lon"] - previo["lon"] + 180.0) % 360.0 - 180.0
        lon = previo["lon"] + delta_lon * fraccion
        if lon > 180.0:
            lon -= 360.0
        elif lon < -180.0:
            lon += 360.0
        estado["lon"] = lon
        estado["altitud_km"] = (
            previo["altitud_km"]
            + (siguiente["altitud_km"] - previo["altitud_km"]) * fraccion
        )
        estado["velocidad_kms"] = (
            previo["velocidad_kms"]
            + (siguiente["velocidad_kms"] - previo["velocidad_kms"]) * fraccion
        )
        estado["radio_km"] = (
            previo["radio_km"]
            + (siguiente["radio_km"] - previo["radio_km"]) * fraccion
        )
        return estado

    def _cargar_cache_tle(self):
        """Recupera TLE recientes del disco para arrancar sin red."""
        try:
            with TLE_CACHE_PATH.open("r", encoding="utf-8") as archivo:
                guardado = json.load(archivo)
            ts = float(guardado.get("ts") or 0.0)
            if not ts or time.time() - ts > TLE_CACHE_MAX_EDAD:
                return
            registros = {}
            for item in guardado.get("tles", []):
                try:
                    registros[int(item["catnr"])] = item
                except (KeyError, TypeError, ValueError):
                    continue

            tles = []
            for config in self._config:
                item = registros.get(int(config["catnr"]))
                if not item:
                    continue
                try:
                    tles.append(_registro_tle(
                        config,
                        _texto(item.get("objeto")),
                        _texto(item.get("linea1")),
                        _texto(item.get("linea2")),
                    ))
                except Exception:
                    continue
            if tles:
                with self._lock:
                    self._tles = tles
                    self._ts_tle = min(ts, time.time())
        except (OSError, ValueError, TypeError):
            return

    @staticmethod
    def _guardar_cache_tle(tles, ts):
        """Guarda línea1/línea2 y un timestamp para el próximo arranque."""
        registros = []
        for tle in tles:
            try:
                registros.append({
                    "catnr": int(tle["catnr"]),
                    "objeto": _texto(tle.get("objeto")),
                    "linea1": str(tle["linea1"]),
                    "linea2": str(tle["linea2"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        if not registros:
            return
        try:
            TLE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporal = TLE_CACHE_PATH.with_suffix(".tmp")
            with temporal.open("w", encoding="utf-8") as archivo:
                json.dump(
                    {"ts": float(ts), "tles": registros},
                    archivo,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            os.replace(temporal, TLE_CACHE_PATH)
        except OSError:
            return

    def _actualizar_tle(self):
        edad = time.time() - self._ts_tle
        ttl = self._ttl
        if self._tles and len(self._tles) < len(self._config):
            ttl = min(ttl, 300.0)
        if self._tles and edad < ttl:
            return
        if self._error and time.time() < self._reintento_ts:
            return

        self._cargando = True
        try:
            datos = descargar_tles(self._config)
        except NasaError as exc:
            with self._lock:
                self._error = str(exc)
                self._reintento_ts = time.time() + TLE_REINTENTO
        except Exception:
            with self._lock:
                self._error = "Error inesperado al descargar los TLE."
                self._reintento_ts = time.time() + TLE_REINTENTO
        else:
            ahora = time.time()
            with self._lock:
                combinados = {tle["catnr"]: tle for tle in self._tles}
                combinados.update({tle["catnr"]: tle for tle in datos})
                self._tles = [
                    combinados[config["catnr"]]
                    for config in self._config
                    if config["catnr"] in combinados
                ]
                self._ts_tle = ahora
                self._error = None
                tles_guardar = list(self._tles)
            self._guardar_cache_tle(tles_guardar, ahora)
        finally:
            self._cargando = False

    def _muestra(self, cuando):
        estados = []
        for tle in tuple(self._tles):
            try:
                estado = propagar_satelite(tle, cuando)
            except Exception:
                continue
            registro = {
                "catnr": tle["catnr"],
                "nombre": tle["nombre"],
                "objeto": tle["objeto"],
                "grupo": tle["grupo"],
                "color": tle["color"],
                "periodo_min": tle["periodo_min"],
                "inclinacion_deg": tle["inclinacion_deg"],
            }
            registro.update(estado)
            estados.append(registro)
        return estados

    def _bucle_tle(self):
        """Descarga TLE sin detener el hilo que muestrea las órbitas."""
        while not self._parado.is_set():
            self._actualizar_tle()
            self._parado.wait(2.0)

    def _bucle(self):
        while not self._parado.is_set():
            try:
                if not self._tles:
                    self._parado.wait(1.0)
                    continue

                t0 = time.time()
                inicio = dt.datetime.fromtimestamp(t0, dt.timezone.utc)
                t1 = t0 + self._intervalo
                fin = dt.datetime.fromtimestamp(t1, dt.timezone.utc)
                muestra_a = self._muestra(inicio)
                muestra_b = self._muestra(fin)
                if muestra_a and muestra_b:
                    with self._lock:
                        self._muestreo = {
                            "t0": t0,
                            "t1": t1,
                            "a": muestra_a,
                            "b": muestra_b,
                        }
            except Exception:
                with self._lock:
                    self._error = "Error inesperado al propagar las órbitas."
                self._parado.wait(2.0)
                continue

            self._parado.wait(self._intervalo)

