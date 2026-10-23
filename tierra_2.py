import datetime
import io
import math
import os
import sys
import time

import numpy as np
import pygame
import pygame.surfarray as surfarray

try:
    from nasa_service import (
        EONET_MODOS,
        NasaService,
        RADIO_TIERRA_KM,
        RastreadorSatelites,
        SAT_RECORTES,
        _gmst,
    )
except ImportError:
    from .nasa_service import (
        EONET_MODOS,
        NasaService,
        RADIO_TIERRA_KM,
        RastreadorSatelites,
        SAT_RECORTES,
        _gmst,
    )


DIR = os.path.dirname(os.path.abspath(__file__))
TEXTURAS = os.path.join(DIR, "textures")

ANCHO, ALTO = 1280, 800
FPS = 60
FONDO = (3, 5, 12)
RADIO_BASE = 0.335
ESCALA_INTERNA = 0.78
MAX_INTERNO = 240
HALO_BASE = 640
ZOOM_MIN, ZOOM_MAX = 0.55, 2.0

COLOR_ACENTO = (0, 195, 255)
COLOR_TEXTO = (170, 205, 230)
COLOR_SECUNDARIO = (100, 130, 160)
COLOR_MARCADOR = (255, 176, 64)
COLOR_ALERTA = (255, 105, 105)
COLOR_SEGURO = (80, 220, 140)
COLOR_EVENTO_DEFECTO = (200, 200, 200)
COLOR_SATELITE = (255, 214, 120)
COLOR_ORBITA = (80, 130, 170)

# Etiqueta en español y color para cada categoría de EONET.
CATEGORIAS_EONET = {
    "wildfires": ("Incendios", (255, 120, 50)),
    "severeStorms": ("Tormentas", (80, 180, 255)),
    "volcanoes": ("Volcanes", (255, 75, 75)),
    "seaLakeIce": ("Hielo marino", (170, 215, 255)),
    "earthquakes": ("Terremotos", (255, 215, 80)),
    "floods": ("Inundaciones", (60, 160, 255)),
    "landslides": ("Deslizamientos", (205, 165, 120)),
    "drought": ("Sequías", (230, 180, 100)),
    "dustHaze": ("Polvo/Calima", (210, 185, 130)),
    "snow": ("Nieve", (220, 235, 255)),
    "temperatureExtremes": ("Temp. extremas", (255, 140, 120)),
    "waterColor": ("Color del agua", (80, 220, 190)),
    "manmade": ("Antrópicos", (200, 200, 200)),
}

TTL_NASA = {"eonet": 300.0, "neows": 6 * 3600.0, "apod": 3600.0}
TTL_SATELITE = 6 * 3600.0
COOLDOWN_NASA = 60.0
CATEGORIAS_METRICA_SATELITE = frozenset({
    "wildfires", "floods", "landslides", "drought",
})
VISOR_ZOOM_MIN = 1.0
VISOR_ZOOM_MAX = 4.0
VISOR_ZOOM_PASO = 1.25


def _normalizar(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


class Tierra:
    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto

        self.yaw = math.radians(-40.0)
        self.pitch = math.radians(16.0)
        self.roll = math.radians(23.44)
        self.zoom = 1.0
        self.zoom_objetivo = 1.0
        self.auto = True
        self.vel_auto = math.radians(1.6)

        self.sol = _normalizar((-0.52, 0.34, 0.78))

        self.mostrar_nubes = True
        self.mostrar_noche = True
        self.mostrar_reticula = False
        self.marcador = None
        self.fps = 0.0

        # Estado de las capas NASA. Las consultas corren en hilos separados y
        # sus resultados se recogen en actualizar() sin bloquear el render.
        self.nasa = NasaService()
        self.nasa_datos = {"eonet": None, "neows": None, "apod": None}
        self.nasa_ts = {"eonet": 0.0, "neows": 0.0, "apod": 0.0}
        self.nasa_intento = {"eonet": 0.0, "neows": 0.0, "apod": 0.0}
        self.nasa_cargando = {"eonet": False, "neows": False, "apod": False}
        self.nasa_error = {"eonet": None, "neows": None, "apod": None}

        # EONET se consulta en dos modos y cada uno conserva su propia caché.
        self.eonet_modo = "activos"
        self._eonet_cache = {
            "activos": {"eventos": None, "ts": 0.0, "error": None},
            "historicos": {"eventos": None, "ts": 0.0, "error": None},
        }
        self._eonet_en_vuelo_modo = None
        self._eonet_pendiente = None

        self.mostrar_eventos = False
        self.mostrar_asteroides = False
        self.mostrar_apod = False

        # Capa de satélites: el rastreador descarga TLE de Celestrak y propaga
        # las órbitas en su propio hilo; aquí solo se interpolan las muestras.
        self.mostrar_satelites = False
        self.rastreador = RastreadorSatelites()
        self.satelites = []
        self.satelites_pantalla = []
        self.satelite_hover_catnr = None
        self.satelite_sel_catnr = None
        self._satelites_panel_rect = pygame.Rect(0, 0, 0, 0)
        self._satelites_filas = []
        self._orbita_cache = (None, [])

        self.eventos = []
        self._eventos_xyz = np.empty((0, 3), dtype=np.float32)
        self._eventos_colores = []
        self.evento_sel = None

        self.apod_thumb = None
        self.apod_thumb_cargando = False
        self.apod_thumb_error = None
        self._apod_imagen_url_intentada = None
        self._apod_imagen_fallida = None

        # La comparación satelital se descarga bajo demanda para el evento
        # seleccionado y se conserva por clave evento/fecha/coordenadas.
        self.satelite_cache = {}
        self.satelite_tex = {}
        self.satelite_full_tex = {}
        self.satelite_error = {}
        self.satelite_intento = {}
        self.satelite_en_vuelo = set()
        self._satelite_hitbox = None
        self._panel_body_top = 0
        self._panel_scroll = 0
        self._panel_scroll_max = 0

        # Visor ampliado de las imágenes satelitales. ``recorte`` es el ancho
        # geográfico descargado; ``zoom`` solo escala lo ya descargado.
        self.visor_satelite_abierto = False
        self.visor_satelite_evento = None
        self.visor_satelite_recorte = SAT_RECORTES[0]
        self.visor_satelite_lado = 0
        self.visor_satelite_zoom = VISOR_ZOOM_MIN
        self.visor_satelite_pan = [0.0, 0.0]
        self.visor_satelite_arrastrando = False
        self.visor_satelite_movido = 0.0
        self.visor_satelite_rect = pygame.Rect(0, 0, 0, 0)
        self.visor_satelite_clave_mostrada = None
        self._visor_cache_key = None
        self._visor_cache = None
        self._visor_rects = {}

        self._nasa_version = 0
        self._nasa_panel = None
        self._nasa_panel_key = None
        self._nasa_panel_rect = pygame.Rect(0, 0, 0, 0)
        self._hud_rect = pygame.Rect(22, 20, 340, 144)
        self._click_panel = False

        self._enfocando = False
        self._obj_yaw = self.yaw
        self._obj_pitch = self.pitch
        self._arrastrando = False
        self._click_pos = None
        self._movido = 0.0

        self._fuente_titulo = pygame.font.SysFont("Consolas", 20, bold=True)
        self._fuente = pygame.font.SysFont("Consolas", 14)
        self._fuente_pequena = pygame.font.SysFont("Consolas", 12)

        self._cargar_texturas()
        self._halo_base = self._crear_halo(HALO_BASE / 3.6)
        self._halo = None
        self._halo_rp = -1
        self._surf_final = None
        self._M = self._matriz()
        self._actualizar_sol()
        self._r = -1
        self._r_pantalla = self._radio()
        self._construir_geometria()
        self._actualizar_halo()
        self._crear_estrellas()

    def _cargar_textura(self, nombre, tam, respaldo):
        ruta = os.path.join(TEXTURAS, nombre)
        if os.path.exists(ruta):
            surf = pygame.image.load(ruta)
            if surf.get_size() != tam:
                surf = pygame.transform.smoothscale(surf, tam)
            arr = surfarray.array3d(surf)
            return np.transpose(arr, (1, 0, 2))
        print(f"[tierra] Falta {ruta}; usando textura de respaldo.")
        arr = np.zeros((tam[1], tam[0], 3), dtype=np.uint8)
        arr[:] = respaldo
        return arr

    def _cargar_nubes(self, tam):
        ruta = os.path.join(TEXTURAS, "earth_clouds.png")
        if os.path.exists(ruta):
            surf = pygame.image.load(ruta).convert_alpha()
            if surf.get_size() != tam:
                surf = pygame.transform.smoothscale(surf, tam)
            alfa = surfarray.array_alpha(surf)
            return np.transpose(alfa, (1, 0))
        return np.zeros((tam[1], tam[0]), dtype=np.uint8)

    def _cargar_texturas(self):
        dia = self._cargar_textura("earth_day.jpg", (1024, 512), (14, 30, 54))
        noche = self._cargar_textura("earth_night.png", (1024, 512), (0, 0, 0))
        brillo = self._cargar_textura("earth_specular.jpg", (1024, 512), (0, 0, 0))
        self.tex = np.concatenate((dia, noche, brillo[:, :, :1]), axis=2)
        self.tex_alto, self.tex_ancho = self.tex.shape[:2]
        self.nubes = self._cargar_nubes((1024, 512))

    def _matriz(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        cr, sr = math.cos(self.roll), math.sin(self.roll)

        ry = np.array([[cy, 0.0, -sy], [0.0, 1.0, 0.0], [sy, 0.0, cy]], dtype=np.float32)
        rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, sp], [0.0, -sp, cp]], dtype=np.float32)
        rz = np.array([[cr, sr, 0.0], [-sr, cr, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        return ry @ rx @ rz

    def _radio(self):
        return max(30, int(min(self.ancho, self.alto) * RADIO_BASE * self.zoom))

    def _radio_interna(self):
        base = int(min(self.ancho, self.alto) * RADIO_BASE * ESCALA_INTERNA)
        return max(24, min(base, MAX_INTERNO))

    def _centro(self):
        return self.ancho // 2, self.alto // 2

    def _construir_geometria(self):
        r = self._radio_interna()
        self._r_pantalla = self._radio()
        if r == self._r:
            return
        self._r = r
        n = 2 * r + 1

        xs = np.linspace(-1.0, 1.0, n, dtype=np.float32)
        nx, ny = np.meshgrid(xs, xs, indexing="ij")
        dist2 = nx * nx + ny * ny
        mascara = dist2 <= 1.0

        self._idx = np.flatnonzero(mascara)
        self._nx = nx[mascara]
        self._ny = ny[mascara]
        self._sz = np.sqrt(np.clip(1.0 - self._nx**2 - self._ny**2, 0.0, 1.0))

        m = self._idx.size
        self._vec = np.empty((3, m), dtype=np.float32)
        self._vec[0] = self._nx
        self._vec[1] = -self._ny
        self._vec[2] = self._sz
        self._loc = np.empty((3, m), dtype=np.float32)
        self._lat = np.empty(m, dtype=np.float32)
        self._lon = np.empty(m, dtype=np.float32)
        self._u = np.empty(m, dtype=np.float32)
        self._v = np.empty(m, dtype=np.float32)
        self._xx = np.empty(m, dtype=np.int32)
        self._yy = np.empty(m, dtype=np.int32)
        self._xxc = np.empty(m, dtype=np.int32)
        self._muestra = np.empty((m, 7), dtype=np.float32)
        self._color = np.empty((m, 3), dtype=np.float32)
        self._tmp3 = np.empty((m, 3), dtype=np.float32)
        self._luz = np.empty(m, dtype=np.float32)
        self._difusa = np.empty(m, dtype=np.float32)
        self._dia_f = np.empty(m, dtype=np.float32)
        self._factor = np.empty(m, dtype=np.float32)
        self._inv = np.empty(m, dtype=np.float32)
        self._esp = np.empty(m, dtype=np.float32)
        self._tmp1 = np.empty(m, dtype=np.float32)

        self._borde = (1.0 - self._sz) ** 3.2
        self._limb = (0.58 + 0.42 * self._sz).astype(np.float32)[:, None]
        self._h_vec = _normalizar(self.sol + np.array([0.0, 0.0, 1.0], dtype=np.float32))
        self._nube_rgb = np.array([0.94, 0.97, 1.0], dtype=np.float32)
        self._atm_px = self._borde[:, None] * np.array([0.078, 0.190, 0.430], dtype=np.float32)
        self._lut_difusa = ((np.arange(256, dtype=np.float32) / 255.0) ** 0.85).astype(np.float32)
        self._idx_lut = np.empty(m, dtype=np.int32)

        cobertura = np.clip((1.0 - np.sqrt(dist2)) * r + 0.5, 0.0, 1.0)
        self._mascara = pygame.Surface((n, n), pygame.SRCALPHA)
        self._mascara.fill((255, 255, 255, 0))
        alfa = surfarray.pixels_alpha(self._mascara)
        alfa[:] = (cobertura * 255.0).astype(np.uint8)
        del alfa

        self._buf = np.zeros((n, n, 3), dtype=np.uint8)
        self._surf_globo = pygame.Surface((n, n))
        self._surf_capa = pygame.Surface((n, n), pygame.SRCALPHA)

    def _crear_halo(self, r):
        n = int(r * 3.6)
        if n % 2:
            n += 1
        eje = np.arange(n, dtype=np.float32) - (n - 1) / 2.0
        xx, yy = np.meshgrid(eje, eje, indexing="xy")
        d = np.sqrt(xx * xx + yy * yy) / (n / 2.0)
        borde = r / (n / 2.0)

        interior = np.clip(1.0 - (d / max(borde, 1e-6)) ** 2, 0.0, 1.0) * 0.06
        exterior = np.exp(-(((d - borde) / 0.22) ** 2)) * 0.32
        alpha = np.clip(interior + exterior, 0.0, 1.0)

        rgb = np.zeros((n, n, 3), dtype=np.float32)
        rgb[..., 0] = alpha * 24.0
        rgb[..., 1] = alpha * 70.0
        rgb[..., 2] = alpha * 150.0

        surf = pygame.Surface((n, n))
        surfarray.blit_array(surf, np.transpose(rgb, (1, 0, 2)).astype(np.uint8))
        return surf

    def _actualizar_halo(self):
        n = int(self._r_pantalla * 3.6)
        if n % 2:
            n += 1
        self._halo = pygame.transform.smoothscale(self._halo_base, (n, n))
        self._halo_rp = self._r_pantalla

    def _crear_estrellas(self):
        surf = pygame.Surface((self.ancho, self.alto))
        surf.fill(FONDO)
        rng = np.random.default_rng(7)
        for _ in range(460):
            x = int(rng.integers(0, self.ancho))
            y = int(rng.integers(0, self.alto))
            brillo = int(rng.integers(28, 150))
            tono = int(rng.integers(-8, 14))
            color = (
                max(0, min(255, brillo + tono)),
                max(0, min(255, brillo)),
                max(0, min(255, brillo + 18)),
            )
            radio = 1 if rng.random() < 0.93 else 2
            pygame.draw.circle(surf, color, (x, y), radio)
        self.estrellas = surf

    def _calcular_indices(self):
        ancho, alto = self.tex_ancho, self.tex_alto
        np.multiply(self._u, ancho, out=self._xx, casting="unsafe")
        np.clip(self._xx, 0, ancho - 1, out=self._xx)
        np.multiply(self._v, alto, out=self._yy, casting="unsafe")
        np.clip(self._yy, 0, alto - 1, out=self._yy)

    def _renderizar_globo(self, t):
        self._r_pantalla = self._radio()
        np.matmul(self._M, self._vec, out=self._loc)

        np.clip(self._loc[1], -1.0, 1.0, out=self._lat)
        np.arcsin(self._lat, out=self._lat)
        np.arctan2(self._loc[0], self._loc[2], out=self._lon)

        np.divide(self._lon, 2.0 * math.pi, out=self._u)
        self._u += 0.5
        np.divide(self._lat, math.pi, out=self._v)
        np.subtract(0.5, self._v, out=self._v)

        self._calcular_indices()
        np.multiply(self.tex[self._yy, self._xx], 1.0 / 255.0, out=self._muestra)
        dia = self._muestra[:, :3]

        np.dot(self.sol, self._vec, out=self._luz)
        np.clip(self._luz, 0.0, 1.0, out=self._difusa)

        np.subtract(self._luz, -0.12, out=self._dia_f)
        self._dia_f *= 1.0 / 0.26
        np.clip(self._dia_f, 0.0, 1.0, out=self._dia_f)
        np.multiply(self._dia_f, -2.0, out=self._tmp1)
        self._tmp1 += 3.0
        np.multiply(self._dia_f, self._dia_f, out=self._dia_f)
        self._dia_f *= self._tmp1

        np.multiply(self._difusa, 255.0, out=self._idx_lut, casting="unsafe")
        np.take(self._lut_difusa, self._idx_lut, out=self._factor)
        self._factor *= 0.95
        self._factor += 0.045
        np.multiply(dia, self._factor[:, None], out=self._color)

        if self.mostrar_noche:
            np.subtract(1.0, self._dia_f, out=self._inv)
            self._inv *= 1.35
            np.multiply(self._muestra[:, 3:6], self._inv[:, None], out=self._tmp3)
            self._color += self._tmp3

        np.dot(self._h_vec, self._vec, out=self._esp)
        self._esp -= 0.965
        self._esp *= 28.0
        np.clip(self._esp, 0.0, 1.0, out=self._esp)
        self._esp *= self._esp
        self._esp *= self._muestra[:, 6]
        self._esp *= self._dia_f
        self._esp *= 0.45
        self._color += self._esp[:, None]

        if self.mostrar_nubes:
            desfase = int(round(0.008 * math.sin(t * 0.05) * self.tex_ancho))
            np.add(self._xx, desfase, out=self._xxc)
            np.subtract(self._xxc, self.tex_ancho, out=self._xxc,
                        where=self._xxc >= self.tex_ancho)
            np.add(self._xxc, self.tex_ancho, out=self._xxc, where=self._xxc < 0)

            np.multiply(self.nubes[self._yy, self._xxc], 0.92 / 255.0, out=self._tmp1)
            a = self._tmp1
            np.subtract(1.0, a, out=self._inv)
            np.multiply(self._color, self._inv[:, None], out=self._color)

            np.multiply(self._difusa, 0.94, out=self._factor)
            self._factor += 0.06
            self._factor *= a
            np.multiply(self._factor[:, None], self._nube_rgb, out=self._tmp3)
            self._color += self._tmp3

        np.multiply(self._color, self._limb, out=self._color)
        self._color += self._atm_px

        np.clip(self._color, 0.0, 1.0, out=self._color)
        self._color *= 255.0
        buf = self._buf.reshape(-1, 3)
        buf[self._idx] = self._color
        surfarray.blit_array(self._surf_globo, self._buf)

        self._surf_capa.blit(self._surf_globo, (0, 0))
        self._surf_capa.blit(self._mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        ancho_final = 2 * self._r_pantalla + 1
        if self._surf_final is None or self._surf_final.get_width() != ancho_final:
            self._surf_final = pygame.Surface((ancho_final, ancho_final), pygame.SRCALPHA)
        pygame.transform.smoothscale(self._surf_capa, (ancho_final, ancho_final), self._surf_final)

        cx, cy = self._centro()
        return (cx - self._r_pantalla, cy - self._r_pantalla)

    def _actualizar_sol(self):
        """Ubica el punto subsolar real y lo lleva al espacio de vista."""
        ahora = datetime.datetime.now(datetime.timezone.utc)
        jd = 2440587.5 + ahora.timestamp() / 86400.0
        n = jd - 2451545.0
        L = math.radians((280.460 + 0.9856474 * n) % 360)
        g = math.radians((357.528 + 0.9856003 * n) % 360)
        lam = (
            L
            + math.radians(1.915) * math.sin(g)
            + math.radians(0.020) * math.sin(2 * g)
        )
        eps = math.radians(23.439 - 4e-7 * n)
        dec = math.asin(math.sin(eps) * math.sin(lam))
        ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
        lon = ra - _gmst(jd)
        mundo = np.array(
            [
                math.cos(dec) * math.sin(lon),
                math.sin(dec),
                math.cos(dec) * math.cos(lon),
            ],
            dtype=np.float32,
        )
        self.sol = _normalizar(self._M.T @ mundo)
        self._h_vec = _normalizar(
            self.sol + np.array([0.0, 0.0, 1.0], dtype=np.float32)
        )

    def _proyectar(self, lat, lon):
        la = math.radians(lat)
        lo = math.radians(lon)
        p = np.array(
            [math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo)],
            dtype=np.float32,
        )
        return self._M.T @ p

    def coordenadas_en(self, x, y):
        cx, cy = self._centro()
        dx = (x - cx) / self._r_pantalla
        dy = (cy - y) / self._r_pantalla
        d2 = dx * dx + dy * dy
        if d2 > 1.0:
            return None
        dz = math.sqrt(1.0 - d2)
        loc = self._M @ np.array([dx, dy, dz], dtype=np.float32)
        lat = math.degrees(math.asin(max(-1.0, min(1.0, float(loc[1])))))
        lon = math.degrees(math.atan2(float(loc[0]), float(loc[2])))
        return lat, lon

    def _preparar_eventos(self):
        """Precalcula vectores y colores para pintar todos los eventos EONET."""
        if self.eventos:
            lats = np.radians([evento["lat"] for evento in self.eventos])
            lons = np.radians([evento["lon"] for evento in self.eventos])
            self._eventos_xyz = np.stack(
                (
                    np.cos(lats) * np.sin(lons),
                    np.sin(lats),
                    np.cos(lats) * np.cos(lons),
                ),
                axis=1,
            ).astype(np.float32)
            self._eventos_colores = [
                CATEGORIAS_EONET.get(
                    evento.get("categoria"), ("Otros", COLOR_EVENTO_DEFECTO)
                )[1]
                for evento in self.eventos
            ]
        else:
            self._eventos_xyz = np.empty((0, 3), dtype=np.float32)
            self._eventos_colores = []

    def _cargar_eventos(self, eventos):
        """Sustituye la lista de eventos y conserva la selección si sigue viva."""
        anterior = self.evento_sel
        self.eventos = eventos if eventos is not None else []
        self._preparar_eventos()

        if anterior is not None:
            nuevo = next(
                (evento for evento in self.eventos
                 if evento.get("id") == anterior.get("id")),
                None,
            )
            if nuevo is None and self.marcador == (anterior.get("lat"), anterior.get("lon")):
                self.marcar(None)
            self.evento_sel = nuevo

        self._solicitar_satelite()
        self._nasa_version += 1

    def _dibujar_eventos(self, pantalla):
        """Pinta eventos EONET con pulso tipo radar en la cara visible."""
        if not self.mostrar_eventos or not self.eventos:
            return

        scr = self._eventos_xyz @ self._M
        visibles = scr[:, 2] > 0.02
        if not np.any(visibles):
            return

        cx, cy = self._centro()
        radio = self._r_pantalla
        t = pygame.time.get_ticks() / 1000.0
        id_sel = self.evento_sel.get("id") if self.evento_sel else None
        denso = len(self.eventos) > 250

        for indice in np.flatnonzero(visibles):
            x = int(cx + scr[indice, 0] * radio)
            y = int(cy - scr[indice, 1] * radio)

            # Fase distinta por evento para que no todos parpadeen al unísono.
            fase = t * 3.1 + indice * 0.67
            pulso = 0.5 + 0.5 * math.sin(fase)
            seleccionado = (
                id_sel is not None
                and self.eventos[indice].get("id") == id_sel
            )
            base = self._eventos_colores[indice]
            brillo = 0.55 + 0.45 * pulso
            color = tuple(min(255, int(c * brillo + 25)) for c in base)
            radio_core = int(round(
                2.0 + 1.4 * pulso + (1.0 if seleccionado else 0.0)
            ))

            if denso and not seleccionado:
                # Un solo círculo por marcador mantiene fluido el modo de 720 eventos.
                pygame.draw.circle(pantalla, color, (x, y), radio_core)
                continue

            color_halo = tuple(
                max(0, int(c * (0.25 + 0.25 * pulso))) for c in base
            )
            radio_halo = int(round(radio_core + 4.0 + 2.5 * pulso))
            pygame.draw.circle(pantalla, (5, 12, 20), (x, y), radio_core + 1)
            pygame.draw.circle(pantalla, color_halo, (x, y), radio_halo, 1)
            pygame.draw.circle(pantalla, color, (x, y), radio_core)
            if seleccionado:
                pygame.draw.circle(
                    pantalla, (255, 255, 255), (x, y), radio_halo + 3, 1
                )

    def _evento_cercano(self, x, y):
        """Devuelve el evento EONET más próximo al clic, si está a menos de 12 px."""
        if not self.mostrar_eventos or not self.eventos:
            return None

        scr = self._eventos_xyz @ self._M
        cx, cy = self._centro()
        radio = self._r_pantalla
        mejor = None
        mejor_d2 = 12.0 ** 2

        for indice in np.flatnonzero(scr[:, 2] > 0.0):
            ex = cx + scr[indice, 0] * radio
            ey = cy - scr[indice, 1] * radio
            d2 = (x - ex) ** 2 + (y - ey) ** 2
            if d2 < mejor_d2:
                mejor_d2 = d2
                mejor = self.eventos[indice]

        return mejor

    @staticmethod
    def _edad_texto(segundos):
        if segundos is None:
            return "sin datos"
        segundos = max(0, int(segundos))
        if segundos < 90:
            return f"{segundos} s"
        if segundos < 3600:
            return f"{segundos // 60} min"
        return f"{segundos // 3600} h {(segundos % 3600) // 60:02d} min"

    def _estado_satelites(self):
        rastreador = self.rastreador
        if rastreador.cargando:
            return "DESCARGANDO TLE DE CELESTRAK..."
        if not self.satelites:
            return rastreador.error or "ESPERANDO TLE DE CELESTRAK..."
        partes = [f"{len(self.satelites)} SATÉLITES"]
        edad = rastreador.edad_tle
        if edad is not None:
            partes.append(f"TLE {self._edad_texto(edad)}")
        if rastreador.error:
            partes.append("REINTENTANDO")
        return " · ".join(partes)

    def _actualizar_satelites(self):
        """Interpola posiciones y las proyecta sin tocar el hilo de render."""
        if not self.mostrar_satelites:
            self.satelites = []
            self.satelites_pantalla = []
            self.satelite_hover_catnr = None
            return

        self.rastreador.iniciar()
        self.satelites = self.rastreador.estados()
        self._proyectar_satelites()
        self._actualizar_hover_satelite()

    def _proyectar_satelites(self):
        if self.satelite_sel_catnr is not None and not any(
            sat.get("catnr") == self.satelite_sel_catnr for sat in self.satelites
        ):
            self.satelite_sel_catnr = None

        cx, cy = self._centro()
        radio = self._r_pantalla
        proyectados = []
        for sat in self.satelites:
            altitud = max(0.0, float(sat.get("altitud_km") or 0.0))
            escala = 1.0 + altitud / RADIO_TIERRA_KM
            lat = math.radians(float(sat.get("lat") or 0.0))
            lon = math.radians(float(sat.get("lon") or 0.0))
            local = np.array(
                [
                    math.cos(lat) * math.sin(lon),
                    math.sin(lat),
                    math.cos(lat) * math.cos(lon),
                ],
                dtype=np.float32,
            )
            vista = (self._M.T @ local) * escala
            px = float(vista[0])
            py = float(vista[1])
            pz = float(vista[2])
            visible = pz >= 0.0 or (px * px + py * py) >= 1.0
            proyectados.append({
                "sat": sat,
                "x": cx + px * radio,
                "y": cy - py * radio,
                "px": px,
                "py": py,
                "pz": pz,
                "escala": escala,
                "visible": visible,
            })
        self.satelites_pantalla = proyectados

    def _actualizar_hover_satelite(self):
        self.satelite_hover_catnr = None
        if (not self.mostrar_satelites or self._arrastrando
                or self._click_panel):
            return
        pos = pygame.mouse.get_pos()
        if (self._hud_rect.collidepoint(pos)
                or self._nasa_panel_rect.collidepoint(pos)
                or self._satelites_panel_rect.collidepoint(pos)):
            return
        item = self._satelite_cercano(*pos)
        if item is not None:
            self.satelite_hover_catnr = item["sat"].get("catnr")

    def _satelite_cercano(self, x, y, radio=16.0):
        mejor = None
        mejor_d2 = radio * radio
        for item in self.satelites_pantalla:
            if not item["visible"]:
                continue
            d2 = (x - item["x"]) ** 2 + (y - item["y"]) ** 2
            if d2 <= mejor_d2:
                mejor_d2 = d2
                mejor = item
        return mejor

    def _item_satelite(self, catnr):
        for item in self.satelites_pantalla:
            if item["sat"].get("catnr") == catnr:
                return item
        return None

    def _dibujar_orbita_satelite(self, pantalla):
        """Anillo orbital del satélite fijado, oculto tras el globo."""
        if self.satelite_sel_catnr is None:
            return
        clave = (self.satelite_sel_catnr, int(pygame.time.get_ticks() // 100))
        if self._orbita_cache[0] != clave:
            self._orbita_cache = (
                clave,
                self.rastreador.orbita(self.satelite_sel_catnr, puntos=96),
            )
        anillo = self._orbita_cache[1]
        if not anillo:
            return

        item = self._item_satelite(self.satelite_sel_catnr)
        color = item["sat"].get("color", COLOR_SATELITE) if item else COLOR_SATELITE
        color = tuple(max(0, int(canal * 0.62)) for canal in color)
        cx, cy = self._centro()
        radio = self._r_pantalla
        puntos = []

        for lat, lon, altitud in anillo:
            escala = 1.0 + max(0.0, float(altitud)) / RADIO_TIERRA_KM
            lat_r = math.radians(lat)
            lon_r = math.radians(lon)
            local = np.array(
                [
                    math.cos(lat_r) * math.sin(lon_r),
                    math.sin(lat_r),
                    math.cos(lat_r) * math.cos(lon_r),
                ],
                dtype=np.float32,
            )
            vista = (self._M.T @ local) * escala
            px, py, pz = float(vista[0]), float(vista[1]), float(vista[2])
            oculto = pz < 0.0 and (px * px + py * py) < 1.0
            if oculto:
                puntos.append(None)
            else:
                puntos.append((int(cx + px * radio), int(cy - py * radio)))

        self._dibujar_runs(pantalla, puntos, color)

    def _dibujar_satelites(self, pantalla):
        if not self.mostrar_satelites or not self.satelites_pantalla:
            return

        t = pygame.time.get_ticks() / 1000.0
        cx, cy = self._centro()
        radio = self._r_pantalla

        for item in self.satelites_pantalla:
            if not item["visible"]:
                continue
            sat = item["sat"]
            color = sat.get("color", COLOR_SATELITE)
            x = int(round(item["x"]))
            y = int(round(item["y"]))
            catnr = sat.get("catnr")
            seleccionado = catnr == self.satelite_sel_catnr
            resaltado = seleccionado or catnr == self.satelite_hover_catnr
            pulso = 0.5 + 0.5 * math.sin(t * 2.8 + (catnr or 0) % 29)

            if seleccionado:
                escala = max(1e-6, item["escala"])
                sx = int(cx + item["px"] / escala * radio)
                sy = int(cy - item["py"] / escala * radio)
                pygame.draw.aaline(pantalla, (54, 96, 128), (sx, sy), (x, y))

            tenue = tuple(max(12, int(canal * 0.5)) for canal in color)
            pygame.draw.circle(pantalla, (4, 10, 18), (x, y), 4)
            pygame.draw.circle(
                pantalla, tenue, (x, y), int(round(7.0 + 2.0 * pulso)), 1
            )
            pygame.draw.lines(
                pantalla,
                color,
                True,
                [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)],
                1,
            )
            pygame.draw.circle(pantalla, (240, 250, 255), (x, y), 1)
            if resaltado:
                pygame.draw.circle(pantalla, (235, 248, 255), (x, y), 11, 1)

    def _dibujar_etiqueta_satelite(self, pantalla, item, seguir_raton=False):
        sat = item["sat"]
        nombre = sat.get("nombre") or sat.get("objeto") or "Satélite"
        grupo = sat.get("grupo") or "NASA"
        detalle = (
            f"ALT {float(sat.get('altitud_km') or 0.0):.1f} km"
            f"  ·  VEL {float(sat.get('velocidad_kms') or 0.0):.2f} km/s"
        )
        titulo = self._fuente.render(f"{nombre} · {grupo}", True, COLOR_TEXTO)
        linea = self._fuente_pequena.render(detalle, True, sat.get("color", COLOR_SATELITE))
        ancho = max(titulo.get_width(), linea.get_width()) + 32
        alto = 42

        if seguir_raton:
            base_x, base_y = pygame.mouse.get_pos()
            base_x += 18
            base_y += 16
        else:
            base_x = int(item["x"]) + 15
            base_y = int(item["y"]) - alto - 12

        # Evita tapar los paneles fijos: prueba arriba/abajo e izquierda/derecha.
        paneles = (
            self._hud_rect,
            self._nasa_panel_rect,
            self._satelites_panel_rect,
        )
        candidatos = (
            (base_x, base_y),
            (base_x - ancho - 33, base_y),
            (base_x, base_y + alto + 24),
            (base_x - ancho - 33, base_y + alto + 24),
        )
        x = max(8, min(self.ancho - ancho - 8, base_x))
        y = max(8, min(self.alto - alto - 8, base_y))
        for candidato_x, candidato_y in candidatos:
            prueba_x = max(8, min(self.ancho - ancho - 8, candidato_x))
            prueba_y = max(8, min(self.alto - alto - 8, candidato_y))
            rect = pygame.Rect(prueba_x, prueba_y, ancho, alto).inflate(8, 8)
            if not any(rect.colliderect(panel) for panel in paneles):
                x, y = prueba_x, prueba_y
                break

        panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.rect(panel, (5, 12, 22, 235), panel.get_rect(), border_radius=7)
        pygame.draw.rect(
            panel, (44, 84, 116, 190), panel.get_rect(), 1, border_radius=7
        )
        pygame.draw.circle(panel, sat.get("color", COLOR_SATELITE), (12, 14), 3)
        panel.blit(titulo, (22, 5))
        panel.blit(linea, (22, 23))
        pantalla.blit(panel, (x, y))

    def _dibujar_etiquetas_satelites(self, pantalla):
        if not self.mostrar_satelites:
            return
        elegido = self._item_satelite(self.satelite_sel_catnr)
        if elegido is not None and elegido["visible"]:
            self._dibujar_etiqueta_satelite(pantalla, elegido)
        hover = self._item_satelite(self.satelite_hover_catnr)
        if (hover is not None and hover["visible"]
                and hover is not elegido):
            self._dibujar_etiqueta_satelite(pantalla, hover, seguir_raton=True)

    def _catnr_fila(self, pos):
        for rect, catnr in self._satelites_filas:
            if rect.collidepoint(pos):
                return catnr
        return None

    def _dibujar_panel_satelites(self, pantalla):
        if not self.mostrar_satelites:
            self._satelites_panel_rect = pygame.Rect(0, 0, 0, 0)
            self._satelites_filas = []
            return

        ancho = 372
        fila_alto = 18
        cabecera = 52
        max_filas = max(2, (self.alto - 300) // fila_alto)
        visibles = self.satelites[:max_filas]
        alto = cabecera + fila_alto * len(visibles)
        if not visibles:
            alto = 90
        recortados = len(self.satelites) - len(visibles)
        if recortados > 0:
            alto += 18

        rect = pygame.Rect(22, self.alto - alto - 22, ancho, alto)
        self._satelites_panel_rect = rect
        self._satelites_filas = []
        self._panel(pantalla, rect, alpha=200)

        pygame.draw.circle(pantalla, COLOR_SATELITE, (rect.x + 20, rect.y + 18), 4)
        pantalla.blit(
            self._fuente.render("SATÉLITES · TIEMPO REAL", True, COLOR_SATELITE),
            (rect.x + 30, rect.y + 9),
        )
        estado = self._recortar(
            self._estado_satelites(), self._fuente_pequena, rect.width - 60
        )
        color_estado = (
            COLOR_ALERTA if self.rastreador.error and not self.satelites
            else COLOR_SECUNDARIO
        )
        pantalla.blit(
            self._fuente_pequena.render(estado, True, color_estado),
            (rect.x + 30, rect.y + 30),
        )

        if not visibles:
            mensaje = (
                self.rastreador.error
                or "Descargando TLE oficiales de Celestrak..."
            )
            y = self._texto_panel(
                pantalla, mensaje, self._fuente_pequena,
                COLOR_ALERTA if self.rastreador.error else COLOR_SECUNDARIO,
                rect.x + 16, rect.y + 52, rect.width - 32, 2,
            )
            return

        raton = pygame.mouse.get_pos()
        y = rect.y + cabecera
        for sat in visibles:
            catnr = sat.get("catnr")
            fila = pygame.Rect(rect.x + 8, y - 3, rect.width - 16, fila_alto - 1)
            self._satelites_filas.append((fila, catnr))
            seleccionado = catnr == self.satelite_sel_catnr
            if seleccionado:
                pygame.draw.rect(pantalla, (18, 44, 64), fila, border_radius=4)
            elif fila.collidepoint(raton):
                pygame.draw.rect(pantalla, (12, 30, 46), fila, border_radius=4)

            color = sat.get("color", COLOR_SATELITE)
            pygame.draw.circle(pantalla, color, (rect.x + 16, y + 6), 3)
            nombre = self._recortar(
                sat.get("nombre", ""), self._fuente_pequena, 150
            )
            pantalla.blit(
                self._fuente_pequena.render(nombre, True, COLOR_TEXTO),
                (rect.x + 26, y),
            )

            altitud = self._fuente_pequena.render(
                f"{float(sat.get('altitud_km') or 0.0):4.0f} km", True, COLOR_TEXTO
            )
            velocidad = self._fuente_pequena.render(
                f"{float(sat.get('velocidad_kms') or 0.0):.2f} km/s", True, color
            )
            pantalla.blit(
                altitud, (rect.x + 252 - altitud.get_width(), y)
            )
            pantalla.blit(
                velocidad, (rect.right - 18 - velocidad.get_width(), y)
            )
            y += fila_alto

        if recortados > 0:
            pantalla.blit(
                self._fuente_pequena.render(
                    f"+{recortados} satélites · amplía la ventana",
                    True, COLOR_SECUNDARIO,
                ),
                (rect.x + 16, y + 2),
            )

    def _dibujar_reticula(self, pantalla):
        cx, cy = self._centro()
        r = self._r_pantalla
        color = (62, 120, 160)

        for lon in range(-180, 180, 30):
            lats = np.linspace(-80.0, 80.0, 121)
            puntos = self._linea_esfera(lats, np.full_like(lats, lon), cx, cy, r)
            self._dibujar_runs(pantalla, puntos, color)

        for lat in range(-60, 61, 30):
            lons = np.linspace(-180.0, 180.0, 181)
            puntos = self._linea_esfera(np.full_like(lons, lat), lons, cx, cy, r)
            self._dibujar_runs(pantalla, puntos, color)

    def _linea_esfera(self, lats, lons, cx, cy, r):
        la = np.radians(lats)
        lo = np.radians(lons)
        x = np.cos(la) * np.sin(lo)
        y = np.sin(la)
        z = np.cos(la) * np.cos(lo)
        scr = self._M.T @ np.stack((x, y, z))
        vis = scr[2] > 0.0
        px = (cx + scr[0] * r).astype(np.int32)
        py = (cy - scr[1] * r).astype(np.int32)
        return [(int(px[i]), int(py[i])) if vis[i] else None for i in range(len(px))]

    def _dibujar_runs(self, pantalla, puntos, color):
        run = []
        for p in puntos:
            if p is None:
                if len(run) > 1:
                    pygame.draw.aalines(pantalla, color, False, run)
                run = []
            else:
                run.append(p)
        if len(run) > 1:
            pygame.draw.aalines(pantalla, color, False, run)

    def _dibujar_marcador(self, pantalla):
        if self.marcador is None:
            return
        lat, lon = self.marcador
        p = self._proyectar(lat, lon)
        if p[2] <= 0.0:
            return
        cx, cy = self._centro()
        x = int(cx + p[0] * self._r_pantalla)
        y = int(cy - p[1] * self._r_pantalla)
        pulso = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.004)
        pygame.draw.circle(pantalla, COLOR_MARCADOR, (x, y), 4)
        pygame.draw.circle(pantalla, (255, 220, 150), (x, y), int(7 + 5 * pulso), 1)
        pygame.draw.circle(pantalla, (255, 200, 100), (x, y), int(13 + 8 * pulso), 1)
        fuente = self._fuente_pequena
        etiqueta = fuente.render(f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}  {abs(lon):.2f}°{'E' if lon >= 0 else 'O'}", True, COLOR_MARCADOR)
        pantalla.blit(etiqueta, (x + 12, y - 18))

    def _panel(self, pantalla, rect, alpha=185):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (5, 12, 22, alpha), panel.get_rect(), border_radius=10)
        pygame.draw.rect(panel, (36, 66, 96, 140), panel.get_rect(), 1, border_radius=10)
        pantalla.blit(panel, rect.topleft)

    def _dibujar_hud(self, pantalla):
        lat = math.degrees(self.pitch)
        lon = (math.degrees(-self.yaw) + 180.0) % 360.0 - 180.0

        alto = 144 if self.mostrar_satelites else 122
        rect = pygame.Rect(22, 20, 340, alto)
        self._hud_rect = rect
        self._panel(pantalla, rect)

        titulo = self._fuente_titulo.render("TIERRA", True, COLOR_ACENTO)
        pantalla.blit(titulo, (rect.x + 16, rect.y + 12))
        sub = self._fuente_pequena.render("NASA BLUE MARBLE  ·  1024 px", True, COLOR_SECUNDARIO)
        pantalla.blit(sub, (rect.x + 92, rect.y + 18))

        pygame.draw.line(pantalla, (30, 55, 80), (rect.x + 16, rect.y + 40), (rect.right - 16, rect.y + 40))

        linea1 = self._fuente.render(
            f"LAT  {abs(lat):6.2f}° {'N' if lat >= 0 else 'S'}    LON  {abs(lon):7.2f}° {'E' if lon >= 0 else 'O'}",
            True, COLOR_TEXTO)
        pantalla.blit(linea1, (rect.x + 16, rect.y + 50))

        estado = "AUTO" if self.auto else "MANUAL"
        linea2 = self._fuente.render(
            f"ZOOM {self.zoom:4.2f}x      GIRO {estado}      FPS {self.fps:3.0f}",
            True, COLOR_SECUNDARIO)
        pantalla.blit(linea2, (rect.x + 16, rect.y + 72))

        if self.mostrar_eventos:
            modo = "ACTIVOS" if self.eonet_modo == "activos" else "HISTÓRICOS"
            texto_marca = f"EONET {modo}  ·  V alterna vista"
            color_marca = (
                COLOR_ACENTO if self.eonet_modo == "activos" else COLOR_MARCADOR
            )
        elif self.marcador is not None:
            mlat, mlon = self.marcador
            texto_marca = (f"MARCADOR  {abs(mlat):.2f}°{'N' if mlat >= 0 else 'S'}"
                           f"   {abs(mlon):.2f}°{'E' if mlon >= 0 else 'O'}")
            color_marca = COLOR_MARCADOR
        else:
            texto_marca = "CLIC EN EL GLOBO PARA MARCAR UN PUNTO"
            color_marca = COLOR_SECUNDARIO

        if self.mostrar_satelites:
            estado = self._recortar(
                self._estado_satelites(), self._fuente_pequena, rect.width - 32
            )
            color_sat = (
                COLOR_ALERTA
                if self.rastreador.error and not self.satelites
                else COLOR_SATELITE
            )
            pantalla.blit(
                self._fuente_pequena.render(estado, True, color_sat),
                (rect.x + 16, rect.y + 96),
            )
            marca_y = rect.y + 118
        else:
            marca_y = rect.y + 96

        pantalla.blit(self._fuente_pequena.render(texto_marca, True, color_marca),
                      (rect.x + 16, marca_y))

    def _estado_capa(self, tipo):
        if self.nasa_cargando.get(tipo):
            return "CARGANDO"
        if self.nasa_error.get(tipo):
            return "ERROR"
        ts = self.nasa_ts.get(tipo, 0.0)
        return "ACT. " + time.strftime("%H:%M", time.localtime(ts)) if ts else ""

    def _aplicar_cache_eonet(self):
        """Muestra en la UI la caché correspondiente al modo EONET actual."""
        cache = self._eonet_cache[self.eonet_modo]
        if cache["eventos"] is not None:
            self.nasa_datos["eonet"] = cache["eventos"]
            self.nasa_ts["eonet"] = cache["ts"]
            self.nasa_error["eonet"] = cache["error"]
            self._cargar_eventos(cache["eventos"])
        else:
            self.nasa_datos["eonet"] = None
            self.nasa_ts["eonet"] = 0.0
            self.nasa_error["eonet"] = None
            self._cargar_eventos([])
        self._nasa_version += 1

    def _alternar_modo_eonet(self):
        """Alterna EONET entre activos (7 días) e históricos (30 días)."""
        self.eonet_modo = (
            "historicos" if self.eonet_modo == "activos" else "activos"
        )
        self._aplicar_cache_eonet()
        cache = self._eonet_cache[self.eonet_modo]
        if (cache["eventos"] is None
                or time.time() - cache["ts"] >= TTL_NASA["eonet"]):
            self._solicitar_nasa("eonet", forzar=True)

    def _solicitar_nasa(self, tipo, forzar=False):
        """Pide datos a NASA respetando caché, clave y peticiones en curso."""
        ahora = time.time()
        if tipo == "eonet":
            cache = self._eonet_cache[self.eonet_modo]
            datos = cache["eventos"]
            ts = cache["ts"]
        else:
            datos = self.nasa_datos.get(tipo)
            ts = self.nasa_ts.get(tipo, 0.0)

        if not forzar and datos is not None and ahora - ts < TTL_NASA[tipo]:
            return

        if tipo in ("neows", "apod") and not self.nasa.tiene_clave:
            mensaje = "Falta NASA_API_KEY en tierra/.env."
            if self.nasa_error.get(tipo) != mensaje:
                self.nasa_error[tipo] = mensaje
                self._nasa_version += 1
            self.nasa_cargando[tipo] = False
            self.nasa_intento[tipo] = ahora
            return

        if self.nasa_cargando.get(tipo):
            if tipo == "eonet" and self._eonet_en_vuelo_modo != self.eonet_modo:
                self._eonet_pendiente = self.eonet_modo
            return

        if tipo == "eonet":
            self._eonet_en_vuelo_modo = self.eonet_modo
            ok = self.nasa.solicitar("eonet", modo=self.eonet_modo)
        else:
            ok = self.nasa.solicitar(tipo)

        if ok:
            self.nasa_cargando[tipo] = True
            self.nasa_error[tipo] = None
            self.nasa_intento[tipo] = ahora
            if tipo == "eonet":
                self._eonet_cache[self.eonet_modo]["error"] = None
            self._nasa_version += 1
        elif tipo == "eonet":
            self._eonet_en_vuelo_modo = None

    def _solicitar_imagen_apod_si_falta(self, forzar=False):
        datos = self.nasa_datos.get("apod")
        if not datos:
            return

        url = datos.get("imagen_url") or ""
        if not url or self.apod_thumb is not None or self.apod_thumb_cargando:
            return
        if self._apod_imagen_fallida == url and not forzar:
            return

        self._apod_imagen_fallida = None
        self.apod_thumb_error = None
        self.apod_thumb_cargando = True
        self._apod_imagen_url_intentada = url
        if not self.nasa.solicitar("apod_imagen", url=url):
            self.apod_thumb_cargando = False
        self._nasa_version += 1

    @staticmethod
    def _clave_satelite(evento, recorte=None):
        """Identifica la comparación satelital de un evento y su recorte."""
        if not evento:
            return None
        base = "|".join(
            str(evento.get(campo, "")) for campo in ("id", "fecha", "lat", "lon")
        )
        if recorte is None or abs(float(recorte) - SAT_RECORTES[0]) < 1e-6:
            return base
        return f"{base}|r{float(recorte):g}"

    def _datos_satelite(self, clave):
        entrada = self.satelite_cache.get(clave)
        return entrada["datos"] if entrada else None

    def _solicitar_satelite(self, forzar=False, recorte=None):
        """Pide la comparación del evento sin bloquear si cambia la selección."""
        evento = self.evento_sel
        if recorte is None:
            recorte = SAT_RECORTES[0]
        recorte = round(float(recorte), 2)
        clave = self._clave_satelite(evento, recorte)
        if clave is None:
            return

        ahora = time.time()
        entrada = self.satelite_cache.get(clave)
        if not forzar and entrada and ahora - entrada["ts"] < TTL_SATELITE:
            return
        if (not forzar and self.satelite_error.get(clave)
                and ahora - self.satelite_intento.get(clave, 0.0) < COOLDOWN_NASA):
            return
        if clave in self.satelite_en_vuelo:
            return

        argumentos = {"evento": evento, "clave": clave}
        if abs(recorte - SAT_RECORTES[0]) >= 1e-6:
            argumentos["recorte"] = recorte
        if self.nasa.solicitar("satelite", **argumentos):
            self.satelite_en_vuelo.add(clave)
            self.satelite_error.pop(clave, None)
            self.satelite_intento[clave] = ahora
            self._nasa_version += 1
        else:
            self.satelite_error[clave] = "No se pudo iniciar la consulta satelital."
            self.satelite_intento[clave] = ahora
            self._nasa_version += 1

    def _cargar_miniaturas_satelite(self, clave, datos):
        try:
            antes = pygame.image.load(io.BytesIO(datos["antes_png"])).convert()
            despues = pygame.image.load(io.BytesIO(datos["despues_png"])).convert()
        except (pygame.error, KeyError, TypeError):
            self.satelite_error[clave] = "No se pudieron mostrar las miniaturas."
            return
        self.satelite_tex[clave] = (antes, despues)

        try:
            antes_full = pygame.image.load(
                io.BytesIO(datos["antes_full_png"])
            ).convert()
            despues_full = pygame.image.load(
                io.BytesIO(datos["despues_full_png"])
            ).convert()
        except (pygame.error, KeyError, TypeError):
            self.satelite_full_tex.pop(clave, None)
        else:
            self.satelite_full_tex[clave] = (antes_full, despues_full)
        self._recortar_cache_texturas_satelite()

    def _recortar_cache_texturas_satelite(self, maximo=6):
        """Limita las cachés satelitales sin descartar la selección actual."""
        protegidas = set()
        if self.evento_sel:
            protegidas.add(self._clave_satelite(self.evento_sel))
        if self.visor_satelite_evento:
            protegidas.add(self._clave_satelite(
                self.visor_satelite_evento, self.visor_satelite_recorte
            ))
        if self.visor_satelite_clave_mostrada:
            protegidas.add(self.visor_satelite_clave_mostrada)

        for cache in (self.satelite_full_tex, self.satelite_tex,
                      self.satelite_cache):
            while len(cache) > maximo:
                sobrante = next(
                    (clave for clave in cache if clave not in protegidas), None
                )
                if sobrante is None:
                    break
                cache.pop(sobrante)

    def _procesar_satelite(self, datos, error):
        """Cachea cada descarga; solo la selección actual se pinta."""
        clave = datos.get("clave") if isinstance(datos, dict) else None
        if clave:
            self.satelite_en_vuelo.discard(clave)

        if error:
            if clave:
                self.satelite_error[clave] = error
                self.satelite_intento[clave] = time.time()
        elif datos and clave:
            self.satelite_cache[clave] = {"datos": datos, "ts": time.time()}
            self.satelite_error.pop(clave, None)
            self._cargar_miniaturas_satelite(clave, datos)
        elif clave:
            self.satelite_error[clave] = "La comparación satelital no devolvió datos."
            self.satelite_intento[clave] = time.time()

        self._nasa_version += 1

    def _procesar_eonet(self, datos, error):
        """Guarda el resultado EONET en su modo y evita respuestas viejas."""
        modo = self._eonet_en_vuelo_modo or self.eonet_modo
        self.nasa_cargando["eonet"] = False
        self._eonet_en_vuelo_modo = None
        cache = self._eonet_cache.get(modo, self._eonet_cache["activos"])

        if error:
            cache["error"] = error
            if modo == self.eonet_modo:
                self.nasa_error["eonet"] = error
            pendiente = self._eonet_pendiente
            self._eonet_pendiente = None
            if pendiente == self.eonet_modo and pendiente != modo:
                self._solicitar_nasa("eonet", forzar=True)
            self._nasa_version += 1
            return

        if datos is None:
            datos = []
        modo_datos = getattr(datos, "modo", modo)
        cache = self._eonet_cache.get(modo_datos, cache)
        cache["eventos"] = datos
        cache["ts"] = time.time()
        cache["error"] = None

        if modo_datos == self.eonet_modo:
            self.nasa_datos["eonet"] = datos
            self.nasa_ts["eonet"] = cache["ts"]
            self.nasa_error["eonet"] = None
            self._cargar_eventos(datos)

        pendiente = self._eonet_pendiente
        self._eonet_pendiente = None
        if pendiente == self.eonet_modo:
            actual = self._eonet_cache[self.eonet_modo]
            if (actual["eventos"] is None
                    or time.time() - actual["ts"] >= TTL_NASA["eonet"]):
                self._solicitar_nasa("eonet", forzar=True)
        self._nasa_version += 1

    def _procesar_nasa(self):
        """Recoge resultados de los hilos y actualiza el estado de la UI."""
        for tipo, datos, error in self.nasa.poll():
            if tipo == "apod_imagen":
                self.apod_thumb_cargando = False
                if error:
                    self.apod_thumb_error = error
                    self._apod_imagen_fallida = self._apod_imagen_url_intentada
                else:
                    actual = (self.nasa_datos.get("apod") or {}).get("imagen_url")
                    if datos and datos.get("url") == actual:
                        try:
                            self.apod_thumb = pygame.image.load(
                                io.BytesIO(datos["png"])
                            ).convert()
                            self.apod_thumb_error = None
                            self._apod_imagen_fallida = None
                        except (pygame.error, KeyError, TypeError):
                            self.apod_thumb = None
                            self.apod_thumb_error = "No se pudo mostrar la imagen APOD."
                            self._apod_imagen_fallida = self._apod_imagen_url_intentada
                self._nasa_version += 1
                continue

            if tipo == "eonet":
                self._procesar_eonet(datos, error)
                continue

            if tipo == "satelite":
                self._procesar_satelite(datos, error)
                continue

            self.nasa_cargando[tipo] = False
            if error:
                self.nasa_error[tipo] = error
                self._nasa_version += 1
                continue

            if tipo == "neows":
                self.nasa_datos[tipo] = datos or {}
                self.nasa_ts[tipo] = time.time()
                self.nasa_error[tipo] = None
                self._nasa_version += 1
            elif tipo == "apod":
                anterior = self.nasa_datos.get("apod") or {}
                self.nasa_datos[tipo] = datos or {}
                self.nasa_ts[tipo] = time.time()
                self.nasa_error[tipo] = None
                if anterior.get("imagen_url") != (datos or {}).get("imagen_url"):
                    self.apod_thumb = None
                    self.apod_thumb_error = None
                    self.apod_thumb_cargando = False
                    self._apod_imagen_fallida = None
                    self._apod_imagen_url_intentada = None
                self._solicitar_imagen_apod_si_falta()
                self._nasa_version += 1

    def _actualizar_nasa(self):
        """Refresca automáticamente las capas activas sin martillear la API."""
        ahora = time.time()
        capas = (
            ("eonet", self.mostrar_eventos),
            ("neows", self.mostrar_asteroides),
            ("apod", self.mostrar_apod),
        )
        for tipo, activo in capas:
            if not activo or self.nasa_cargando[tipo]:
                continue
            if ahora - self.nasa_intento[tipo] < COOLDOWN_NASA:
                continue

            if tipo == "eonet":
                cache = self._eonet_cache[self.eonet_modo]
                datos = cache["eventos"]
                ts = cache["ts"]
            else:
                datos = self.nasa_datos.get(tipo)
                ts = self.nasa_ts[tipo]

            if datos is None or ahora - ts >= TTL_NASA[tipo]:
                self._solicitar_nasa(tipo)

    def _alternar_capa(self, tipo):
        if tipo == "satelites":
            self.mostrar_satelites = not self.mostrar_satelites
            if self.mostrar_satelites:
                self.rastreador.iniciar()
            else:
                self.satelite_hover_catnr = None
            self._nasa_version += 1
            return

        if tipo == "eonet":
            self.mostrar_eventos = not self.mostrar_eventos
            activo = self.mostrar_eventos
        elif tipo == "neows":
            self.mostrar_asteroides = not self.mostrar_asteroides
            activo = self.mostrar_asteroides
        elif tipo == "apod":
            self.mostrar_apod = not self.mostrar_apod
            activo = self.mostrar_apod
        else:
            return

        self._nasa_version += 1
        if activo:
            self._solicitar_nasa(tipo)
            if tipo == "apod":
                self._solicitar_imagen_apod_si_falta(forzar=True)

    def _recortar(self, texto, fuente, ancho):
        texto = str(texto)
        if fuente.size(texto)[0] <= ancho:
            return texto
        while texto and fuente.size(texto + "...")[0] > ancho:
            texto = texto[:-1]
        return texto.rstrip() + "..."

    def _envolver(self, texto, fuente, ancho, max_lineas=None):
        """Ajusta texto a un ancho en píxeles, con límite opcional de líneas."""
        palabras = str(texto).split()
        if not palabras:
            return []

        lineas = []
        actual = ""
        for palabra in palabras:
            prueba = f"{actual} {palabra}".strip()
            if not actual or fuente.size(prueba)[0] <= ancho:
                actual = prueba
            else:
                lineas.append(actual)
                if max_lineas and len(lineas) >= max_lineas:
                    actual = palabra
                    break
                actual = palabra

        if actual and (not max_lineas or len(lineas) < max_lineas):
            lineas.append(actual)

        if lineas and fuente.size(lineas[-1])[0] > ancho:
            lineas[-1] = self._recortar(lineas[-1], fuente, ancho)

        if max_lineas and len(lineas) >= max_lineas:
            mostradas = sum(len(linea.split()) for linea in lineas)
            if mostradas < len(palabras):
                lineas[-1] = self._recortar(lineas[-1] + "...", fuente, ancho)

        return lineas

    def _texto_panel(self, surface, texto, fuente, color, x, y,
                     ancho=None, max_lineas=None):
        if not texto:
            return y
        if ancho is None:
            surface.blit(fuente.render(str(texto), True, color), (x, y))
            return y + fuente.get_linesize()

        for linea in self._envolver(texto, fuente, ancho, max_lineas):
            surface.blit(fuente.render(linea, True, color), (x, y))
            y += fuente.get_linesize()
        return y

    def _cabecera_panel(self, surface, titulo, estado, x, y, ancho, color):
        pygame.draw.circle(surface, color, (x + 4, y + 7), 4)
        surface.blit(self._fuente.render(titulo, True, color), (x + 14, y))
        if estado:
            etiqueta = self._fuente_pequena.render(estado, True, COLOR_SECUNDARIO)
            surface.blit(etiqueta, (x + ancho - etiqueta.get_width(), y + 2))
        return y + 22

    def _seccion_eonet(self, surface, x, y, ancho):
        y = self._cabecera_panel(
            surface, "EONET · EVENTOS NATURALES", self._estado_capa("eonet"),
            x, y, ancho, COLOR_ACENTO,
        )
        dias = EONET_MODOS[self.eonet_modo]["dias"]
        if self.eonet_modo == "activos":
            modo_texto = "ACTIVOS · 7 DÍAS"
            modo_color = COLOR_ACENTO
        else:
            modo_texto = "HISTÓRICOS · 30 DÍAS"
            modo_color = COLOR_MARCADOR
        y = self._texto_panel(
            surface, f"MODO {modo_texto} · V cambia", self._fuente_pequena,
            modo_color, x, y, ancho, 1,
        )

        if not self.eventos and self.nasa_error["eonet"]:
            y = self._texto_panel(
                surface, self.nasa_error["eonet"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 2,
            )
            return self._texto_panel(
                surface, "Pulsa E para reintentar.", self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )

        if not self.eventos:
            if self.nasa_cargando["eonet"]:
                return self._texto_panel(
                    surface, "Consultando eventos naturales...",
                    self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 2,
                )
            return self._texto_panel(
                surface, f"Sin eventos en los últimos {dias} días.",
                self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 2,
            )

        conteo = {}
        for evento in self.eventos:
            categoria = evento.get("categoria", "otros")
            conteo[categoria] = conteo.get(categoria, 0) + 1

        resumen = " · ".join(
            f"{CATEGORIAS_EONET.get(categoria, ('Otros', COLOR_EVENTO_DEFECTO))[0]} {n}"
            for categoria, n in sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        y = self._texto_panel(
            surface, f"{len(self.eventos)} eventos · {dias} días",
            self._fuente_pequena, COLOR_TEXTO, x, y, ancho, 1,
        )
        y = self._texto_panel(
            surface, resumen, self._fuente_pequena, COLOR_SECUNDARIO,
            x, y, ancho, 2,
        )

        if self.nasa_error["eonet"]:
            y = self._texto_panel(
                surface, self.nasa_error["eonet"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 1,
            )

        if self.evento_sel is None:
            return self._texto_panel(
                surface, "Clic en un marcador para ver detalles.",
                self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 1,
            )

        evento = self.evento_sel
        etiqueta, color = CATEGORIAS_EONET.get(
            evento.get("categoria"), ("Otros", COLOR_EVENTO_DEFECTO)
        )
        pygame.draw.circle(surface, color, (x + 4, y + 7), 4)
        y = self._texto_panel(
            surface, "SELECCIONADO", self._fuente_pequena, COLOR_SECUNDARIO,
            x + 14, y, ancho - 14, 1,
        )
        y = self._texto_panel(
            surface, evento.get("titulo", ""), self._fuente, COLOR_TEXTO,
            x, y + 2, ancho, 2,
        )
        estado = evento.get("estado") or "activo"
        y = self._texto_panel(
            surface,
            f"{etiqueta} · {estado} · {evento.get('fecha') or 'sin fecha'}",
            self._fuente_pequena, color, x, y, ancho, 1,
        )
        return self._seccion_satelite(surface, x, y + 4, ancho, evento)

    @staticmethod
    def _nombre_capa_satelite(capa):
        nombre = str(capa or "").replace("_CorrectedReflectance_TrueColor", "")
        return nombre.replace("_", " ")

    @staticmethod
    def _fecha_etiqueta_satelite(fecha):
        texto = str(fecha or "")
        if len(texto) >= 10:
            return f"{texto[8:10]}/{texto[5:7]}"
        return texto

    def _seccion_satelite(self, surface, x, y, ancho, evento):
        """Miniaturas Antes/Después y estimación del cambio territorial."""
        clave = self._clave_satelite(evento)
        datos = self._datos_satelite(clave)
        error = self.satelite_error.get(clave)
        if clave in self.satelite_en_vuelo:
            estado = "CARGANDO"
        elif error:
            estado = "ERROR"
        else:
            estado = ""
        y = self._cabecera_panel(
            surface, "SATÉLITE · ANTES / DESPUÉS", estado, x, y, ancho,
            COLOR_MARCADOR,
        )

        if not datos:
            if error:
                mensaje = error
                color = COLOR_ALERTA
            elif clave in self.satelite_en_vuelo:
                mensaje = "Descargando y comparando imágenes satelitales..."
                color = COLOR_SECUNDARIO
            else:
                mensaje = "Sin comparación satelital disponible."
                color = COLOR_SECUNDARIO
            return self._texto_panel(
                surface, mensaje, self._fuente_pequena, color, x, y, ancho, 3,
            )

        miniaturas = self.satelite_tex.get(clave)
        if miniaturas is None:
            return self._texto_panel(
                surface, error or "Preparando miniaturas satelitales...",
                self._fuente_pequena,
                COLOR_ALERTA if error else COLOR_SECUNDARIO,
                x, y, ancho, 2,
            )

        lado = min(160, (ancho - 8) // 2, max(90, self.alto // 5))
        antes, despues = miniaturas
        antes = pygame.transform.smoothscale(antes, (lado, lado))
        despues = pygame.transform.smoothscale(despues, (lado, lado))

        fecha_antes = datos.get("antes_fecha", "")
        fecha_despues = datos.get("despues_fecha", "")
        etiqueta_antes = f"ANTES · {fecha_antes}"
        etiqueta_despues = f"DESPUÉS · {fecha_despues}"
        if self._fuente_pequena.size(etiqueta_antes)[0] > lado:
            etiqueta_antes = f"ANTES · {self._fecha_etiqueta_satelite(fecha_antes)}"
        if self._fuente_pequena.size(etiqueta_despues)[0] > lado:
            etiqueta_despues = f"DESPUÉS · {self._fecha_etiqueta_satelite(fecha_despues)}"
        etiqueta_antes = self._recortar(etiqueta_antes, self._fuente_pequena, lado)
        etiqueta_despues = self._recortar(etiqueta_despues, self._fuente_pequena, lado)

        surface.blit(
            self._fuente_pequena.render(etiqueta_antes, True, COLOR_ACENTO), (x, y)
        )
        surface.blit(
            self._fuente_pequena.render(etiqueta_despues, True, COLOR_MARCADOR),
            (x + lado + 8, y),
        )
        y += self._fuente_pequena.get_linesize() + 2

        surface.blit(antes, (x, y))
        surface.blit(despues, (x + lado + 8, y))
        pygame.draw.rect(surface, COLOR_ACENTO, (x, y, lado, lado), 1)
        pygame.draw.rect(surface, COLOR_MARCADOR, (x + lado + 8, y, lado, lado), 1)
        self._satelite_hitbox = pygame.Rect(x, y, lado * 2 + 8, lado)

        for bx in (x, x + lado + 8):
            cx = bx + lado - 11
            cy = y + 11
            pygame.draw.circle(surface, (6, 18, 30), (cx, cy), 9)
            pygame.draw.circle(surface, COLOR_ACENTO, (cx, cy), 9, 1)
            icono = self._fuente_pequena.render("+", True, COLOR_ACENTO)
            surface.blit(
                icono,
                (cx - icono.get_width() // 2, cy - icono.get_height() // 2),
            )

        y += lado + 6

        if evento.get("categoria") in CATEGORIAS_METRICA_SATELITE:
            cambio = float(datos.get("cambio_pct") or 0.0)
            severidad = float(datos.get("severidad") or 0.0)
            if cambio >= 25.0:
                color_cambio = COLOR_ALERTA
            elif cambio >= 8.0:
                color_cambio = COLOR_MARCADOR
            else:
                color_cambio = COLOR_SEGURO
            y = self._texto_panel(
                surface, f"Cambio visual estimado: {cambio:.1f}%",
                self._fuente_pequena, color_cambio, x, y, ancho, 1,
            )
            y = self._texto_panel(
                surface,
                f"Severidad visual estimada: {severidad:.1f}/100",
                self._fuente_pequena, COLOR_TEXTO, x, y, ancho, 1,
            )
            y = self._texto_panel(
                surface,
                "Heurística visual; nubes y humo pueden afectar el resultado.",
                self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 2,
            )
        cobertura = int(round(float(datos.get("cobertura") or 0.0) * 100))
        capa = self._nombre_capa_satelite(datos.get("capa"))
        y = self._texto_panel(
            surface, f"GIBS · {capa} · cobertura válida {cobertura}%",
            self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 1,
        )
        if error:
            y = self._texto_panel(
                surface, error, self._fuente_pequena, COLOR_ALERTA,
                x, y, ancho, 2,
            )
        return y

    def _abrir_visor_satelite(self, lado=0):
        """Abre el visor ampliado sobre la selección actual."""
        if not self.evento_sel:
            return
        self.visor_satelite_evento = self.evento_sel
        self.visor_satelite_recorte = SAT_RECORTES[0]
        self.visor_satelite_lado = 1 if lado else 0
        self.visor_satelite_zoom = VISOR_ZOOM_MIN
        self.visor_satelite_pan = [0.0, 0.0]
        self.visor_satelite_arrastrando = False
        self.visor_satelite_movido = 0.0
        self.visor_satelite_abierto = True
        clave = self._clave_satelite(self.evento_sel)
        self.visor_satelite_clave_mostrada = (
            clave if clave in self.satelite_full_tex else None
        )
        self.visor_satelite_rect = pygame.Rect(0, 0, 0, 0)
        self._visor_cache_key = None
        self._visor_cache = None
        self._visor_rects = {}
        self._click_panel = False

    def _cerrar_visor_satelite(self):
        self.visor_satelite_abierto = False
        self.visor_satelite_evento = None
        self.visor_satelite_arrastrando = False
        self.visor_satelite_rect = pygame.Rect(0, 0, 0, 0)
        self.visor_satelite_clave_mostrada = None
        self._visor_cache_key = None
        self._visor_cache = None
        self._visor_rects = {}

    def _intentar_abrir_visor(self, pos, boton=1):
        """Traduce el hitbox interno del panel a coordenadas de pantalla."""
        if not self._satelite_hitbox or not self.evento_sel:
            return False
        hb = self._satelite_hitbox
        x = self._nasa_panel_rect.x + hb.x
        y = (
            self._nasa_panel_rect.y
            + self._panel_body_top
            + hb.y
            - self._panel_scroll
        )
        if pos[1] < self._nasa_panel_rect.y + self._panel_body_top:
            return False
        rect = pygame.Rect(x, y, hb.width, hb.height)
        if not rect.collidepoint(pos):
            return False
        lado = 1 if boton == 3 or pos[0] >= rect.centerx else 0
        self._abrir_visor_satelite(lado)
        return True

    def _cambiar_recorte_visor(self, recorte):
        recorte = round(float(recorte), 2)
        if abs(recorte - self.visor_satelite_recorte) < 1e-6:
            return
        self.visor_satelite_recorte = recorte
        self.visor_satelite_zoom = VISOR_ZOOM_MIN
        self.visor_satelite_pan = [0.0, 0.0]
        self.visor_satelite_arrastrando = False
        self._visor_cache_key = None
        self._solicitar_satelite(recorte=recorte)

    def _limitar_pan_visor(self):
        vista = self.visor_satelite_rect
        if vista.width <= 0:
            return
        escala = max(1, int(round(vista.width * self.visor_satelite_zoom)))
        max_pan = max(0, (escala - vista.width) // 2)
        self.visor_satelite_pan[0] = max(
            -max_pan, min(max_pan, self.visor_satelite_pan[0])
        )
        self.visor_satelite_pan[1] = max(
            -max_pan, min(max_pan, self.visor_satelite_pan[1])
        )

    def _boton_visor(self, pantalla, rect, texto, activo, color=COLOR_ACENTO):
        fondo = (9, 34, 52) if activo else (7, 17, 29)
        pygame.draw.rect(pantalla, fondo, rect, border_radius=5)
        pygame.draw.rect(
            pantalla, color if activo else (36, 66, 96), rect, 1,
            border_radius=5,
        )
        etiqueta = self._fuente_pequena.render(
            texto, True, color if activo else COLOR_TEXTO
        )
        pantalla.blit(
            etiqueta,
            (
                rect.centerx - etiqueta.get_width() // 2,
                rect.centery - etiqueta.get_height() // 2,
            ),
        )

    def _manejar_evento_visor(self, ev):
        """El visor es modal: consume los eventos del globo mientras está abierto."""
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self._cerrar_visor_satelite()
            return True

        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button not in (1, 3):
                return True
            rects = self._visor_rects
            if rects.get("cerrar") and rects["cerrar"].collidepoint(ev.pos):
                self._cerrar_visor_satelite()
                return True
            if rects.get("antes") and rects["antes"].collidepoint(ev.pos):
                self.visor_satelite_lado = 0
                return True
            if rects.get("despues") and rects["despues"].collidepoint(ev.pos):
                self.visor_satelite_lado = 1
                return True
            for recorte, rect in rects.get("recortes", ()):
                if rect.collidepoint(ev.pos):
                    self._cambiar_recorte_visor(recorte)
                    return True
            panel = rects.get("panel")
            vista = self.visor_satelite_rect
            if not panel or not panel.collidepoint(ev.pos):
                self._cerrar_visor_satelite()
                return True
            if ev.button == 1 and vista.collidepoint(ev.pos):
                self.visor_satelite_arrastrando = True
                self.visor_satelite_movido = 0.0
            return True

        if ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                self.visor_satelite_arrastrando = False
            return True

        if ev.type == pygame.MOUSEMOTION and self.visor_satelite_arrastrando:
            dx, dy = ev.rel
            self.visor_satelite_movido += abs(dx) + abs(dy)
            self.visor_satelite_pan[0] += dx
            self.visor_satelite_pan[1] += dy
            self._limitar_pan_visor()
            return True

        if ev.type == pygame.MOUSEWHEEL:
            if ev.y:
                self.visor_satelite_zoom = max(
                    VISOR_ZOOM_MIN,
                    min(
                        VISOR_ZOOM_MAX,
                        self.visor_satelite_zoom * (VISOR_ZOOM_PASO ** ev.y),
                    ),
                )
                self._visor_cache_key = None
                self._limitar_pan_visor()
            return True

        return True

    def _dibujar_visor_satelite(self, pantalla):
        """Dibuja el modal con precarga de la imagen y sus controles."""
        if not self.visor_satelite_abierto or not self.visor_satelite_evento:
            return
        ancho, alto = pantalla.get_size()
        vw = min(ancho - 48, 1400)
        vh = min(alto - 48, 920)
        panel = pygame.Rect((ancho - vw) // 2, (alto - vh) // 2, vw, vh)
        self._visor_rects = {"panel": panel}

        velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        velo.fill((2, 6, 14, 225))
        pantalla.blit(velo, (0, 0))
        pygame.draw.rect(pantalla, (5, 12, 22), panel, border_radius=12)
        pygame.draw.rect(pantalla, (36, 66, 96), panel, 1, border_radius=12)

        margen = 20
        evento = self.visor_satelite_evento
        pantalla.blit(
            self._fuente_titulo.render("VISOR SATELITAL", True, COLOR_ACENTO),
            (panel.x + margen, panel.y + 12),
        )
        titulo = self._recortar(
            evento.get("titulo", ""), self._fuente, panel.width - 110
        )
        pantalla.blit(
            self._fuente.render(titulo, True, COLOR_TEXTO),
            (panel.x + margen, panel.y + 38),
        )

        cerrar = pygame.Rect(panel.right - 44, panel.y + 12, 28, 28)
        self._visor_rects["cerrar"] = cerrar
        self._boton_visor(pantalla, cerrar, "X", True, COLOR_ALERTA)

        antes = pygame.Rect(panel.x + margen, panel.y + 68, 106, 28)
        despues = pygame.Rect(antes.right + 8, antes.y, 116, 28)
        self._visor_rects["antes"] = antes
        self._visor_rects["despues"] = despues
        self._boton_visor(
            pantalla, antes, "ANTES", self.visor_satelite_lado == 0,
            COLOR_ACENTO,
        )
        self._boton_visor(
            pantalla, despues, "DESPUÉS", self.visor_satelite_lado == 1,
            COLOR_MARCADOR,
        )

        area_img = pygame.Rect(
            panel.x + margen,
            panel.y + 96,
            panel.width - margen * 2,
            max(1, panel.height - 96 - 94),
        )
        lado = max(1, min(area_img.width, area_img.height))
        vista = pygame.Rect(
            area_img.centerx - lado // 2,
            area_img.centery - lado // 2,
            lado,
            lado,
        )
        self.visor_satelite_rect = vista

        recorte = self.visor_satelite_recorte
        clave = self._clave_satelite(evento, recorte)
        actual = self.satelite_full_tex.get(clave)
        datos_actual = self._datos_satelite(clave)
        error_actual = self.satelite_error.get(clave)
        cargando_actual = clave in self.satelite_en_vuelo

        if actual is not None:
            clave_mostrada = clave
            self.visor_satelite_clave_mostrada = clave
        else:
            clave_mostrada = self.visor_satelite_clave_mostrada
        texturas = self.satelite_full_tex.get(clave_mostrada)
        datos_mostrados = (
            self._datos_satelite(clave_mostrada) or datos_actual
        )

        pygame.draw.rect(pantalla, (2, 7, 14), vista)
        if texturas is not None:
            indice = 1 if self.visor_satelite_lado else 0
            textura = texturas[indice]
            escala = max(1, int(round(vista.width * self.visor_satelite_zoom)))
            escala = min(4096, escala)
            clave_cache = (clave_mostrada, indice, vista.width, escala)
            if (clave_cache != self._visor_cache_key
                    or self._visor_cache is None):
                try:
                    self._visor_cache = pygame.transform.smoothscale(
                        textura, (escala, escala)
                    )
                except pygame.error:
                    self._visor_cache = pygame.transform.scale(
                        textura, (escala, escala)
                    )
                self._visor_cache_key = clave_cache
            self._limitar_pan_visor()
            px = (
                vista.centerx - escala // 2
                + int(self.visor_satelite_pan[0])
            )
            py = (
                vista.centery - escala // 2
                + int(self.visor_satelite_pan[1])
            )
            pantalla.set_clip(vista)
            pantalla.blit(self._visor_cache, (px, py))
            pantalla.set_clip(None)

            etiqueta = "ANTES" if indice == 0 else "DESPUÉS"
            fecha = ""
            if datos_mostrados:
                fecha = datos_mostrados.get(
                    "antes_fecha" if indice == 0 else "despues_fecha", ""
                )
            texto_fecha = f"{etiqueta} · {fecha}" if fecha else etiqueta
            color_lado = COLOR_ACENTO if indice == 0 else COLOR_MARCADOR
            img = self._fuente_pequena.render(texto_fecha, True, color_lado)
            fondo = pygame.Surface(
                (img.get_width() + 12, img.get_height() + 6),
                pygame.SRCALPHA,
            )
            fondo.fill((4, 12, 22, 220))
            pos = (vista.x + 8, vista.y + 8)
            pantalla.blit(fondo, pos)
            pygame.draw.rect(
                pantalla, color_lado,
                (pos[0], pos[1], fondo.get_width(), fondo.get_height()), 1,
            )
            pantalla.blit(img, (pos[0] + 6, pos[1] + 3))

            if cargando_actual:
                carga = f"CARGANDO RECORTE {recorte:g}°"
                img = self._fuente_pequena.render(carga, True, COLOR_ACENTO)
                fondo = pygame.Surface(
                    (img.get_width() + 12, img.get_height() + 6),
                    pygame.SRCALPHA,
                )
                fondo.fill((4, 12, 22, 225))
                pos = (
                    vista.centerx - fondo.get_width() // 2,
                    vista.y + 8,
                )
                pantalla.blit(fondo, pos)
                pygame.draw.rect(
                    pantalla, COLOR_ACENTO,
                    (pos[0], pos[1], fondo.get_width(), fondo.get_height()), 1,
                )
                pantalla.blit(img, (pos[0] + 6, pos[1] + 3))

            if error_actual:
                texto_error = self._recortar(
                    error_actual, self._fuente_pequena, vista.width - 16
                )
                img = self._fuente_pequena.render(
                    texto_error, True, COLOR_ALERTA
                )
                pantalla.blit(img, (vista.x + 8, vista.bottom - 22))
        else:
            if error_actual:
                mensaje = error_actual
                color = COLOR_ALERTA
            elif cargando_actual:
                mensaje = "CARGANDO IMAGEN SATELITAL..."
                color = COLOR_SECUNDARIO
            else:
                mensaje = "IMAGEN AMPLIADA NO DISPONIBLE"
                color = COLOR_SECUNDARIO
            lineas = self._envolver(
                mensaje, self._fuente, vista.width - 32, 3
            )
            alto_total = len(lineas) * self._fuente.get_linesize()
            ly = vista.centery - alto_total // 2
            for linea in lineas:
                img = self._fuente.render(linea, True, color)
                pantalla.blit(
                    img, (vista.centerx - img.get_width() // 2, ly)
                )
                ly += self._fuente.get_linesize()

        pygame.draw.rect(
            pantalla, COLOR_ACENTO if self.visor_satelite_lado == 0
            else COLOR_MARCADOR, vista, 1,
        )

        capa = self._nombre_capa_satelite(
            datos_mostrados.get("capa") if datos_mostrados else ""
        )
        info = f"GIBS · {capa or 'sin capa'} · recorte {recorte:g}°"
        if datos_mostrados:
            cobertura = int(round(
                float(datos_mostrados.get("cobertura") or 0.0) * 100
            ))
            info += f" · cobertura {cobertura}%"
        info = self._recortar(
            info, self._fuente_pequena, panel.width - margen * 2
        )
        pantalla.blit(
            self._fuente_pequena.render(info, True, COLOR_SECUNDARIO),
            (panel.x + margen, panel.bottom - 82),
        )

        y_botones = panel.bottom - 56
        etiqueta = self._fuente_pequena.render("RECORTE", True, COLOR_SECUNDARIO)
        pantalla.blit(etiqueta, (panel.x + margen, y_botones + 7))
        bx = panel.x + margen + etiqueta.get_width() + 8
        self._visor_rects["recortes"] = []
        for valor in SAT_RECORTES:
            rect = pygame.Rect(bx, y_botones, 68, 26)
            activo = abs(valor - recorte) < 1e-6
            self._boton_visor(pantalla, rect, f"{valor:g}°", activo)
            self._visor_rects["recortes"].append((valor, rect))
            bx = rect.right + 6

        ayuda = (
            f"Zoom {self.visor_satelite_zoom:.1f}x · "
            "Rueda: zoom · Arrastrar: mover · ESC: cerrar"
        )
        ayuda = self._recortar(
            ayuda, self._fuente_pequena, panel.width - margen * 2
        )
        pantalla.blit(
            self._fuente_pequena.render(ayuda, True, COLOR_SECUNDARIO),
            (panel.x + margen, panel.bottom - 18),
        )

    @staticmethod
    def _formatear_distancia_ld(distancia_ld):
        if distancia_ld is None:
            return "distancia desconocida"
        if distancia_ld < 0.01:
            return "menos de 0.01 LD"
        return f"{distancia_ld:.2f} LD / {distancia_ld * 0.00256956:.5f} AU"

    @staticmethod
    def _formatear_tamano(diametro_min, diametro_max):
        if diametro_min is None and diametro_max is None:
            return "tamaño desconocido"
        if diametro_min is None:
            diametro_min = diametro_max
        if diametro_max is None:
            diametro_max = diametro_min
        if max(diametro_min, diametro_max) < 1.0:
            return (f"{diametro_min * 1000:.0f}"
                    f"-{diametro_max * 1000:.0f} m")
        return f"{diametro_min:.1f}-{diametro_max:.1f} km"

    def _seccion_neows(self, surface, x, y, ancho, max_objetos=5):
        y = self._cabecera_panel(
            surface, "NEOWS · ASTEROIDES", self._estado_capa("neows"),
            x, y, ancho, COLOR_MARCADOR,
        )
        datos = self.nasa_datos.get("neows")

        if not datos and self.nasa_error["neows"]:
            y = self._texto_panel(
                surface, self.nasa_error["neows"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 2,
            )
            return self._texto_panel(
                surface, "Pulsa A para reintentar.", self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )

        if not datos:
            mensaje = ("Consultando NeoWs..." if self.nasa_cargando["neows"]
                       else "Sin datos de asteroides.")
            return self._texto_panel(
                surface, mensaje, self._fuente_pequena, COLOR_SECUNDARIO,
                x, y, ancho, 1,
            )

        y = self._texto_panel(
            surface,
            f"{datos.get('total', 0)} NEOs · 7 días · distancia lunar / tamaño",
            self._fuente_pequena, COLOR_TEXTO, x, y, ancho, 1,
        )
        y = self._texto_panel(
            surface,
            "PHA = clasificación técnica por tamaño y distancia orbital, "
            "no predicción de impacto.",
            self._fuente_pequena, COLOR_SECUNDARIO, x, y, ancho, 2,
        )

        for objeto in datos.get("objetos", [])[:max_objetos]:
            peligroso = bool(objeto.get("peligroso"))
            if peligroso:
                etiqueta = "PHA (clasif. NASA)"
                color_estado = COLOR_ALERTA
            else:
                etiqueta = "No PHA"
                color_estado = COLOR_SEGURO

            badge = self._fuente_pequena.render(etiqueta, True, color_estado)
            ancho_nombre = max(40, ancho - badge.get_width() - 8)
            nombre = self._recortar(
                objeto.get("nombre", ""), self._fuente_pequena, ancho_nombre
            )
            surface.blit(
                self._fuente_pequena.render(nombre, True, COLOR_TEXTO), (x, y)
            )
            surface.blit(badge, (x + ancho - badge.get_width(), y))
            y += self._fuente_pequena.get_linesize()

            velocidad = (f"{objeto['velocidad_kms']:.1f} km/s"
                         if objeto.get("velocidad_kms") is not None
                         else "velocidad desconocida")
            tamano = self._formatear_tamano(
                objeto.get("diametro_min_km"),
                objeto.get("diametro_max_km"),
            )
            detalle = (
                f"{self._formatear_distancia_ld(objeto.get('distancia_ld'))}"
                f" · {tamano} · {velocidad}"
            )
            y = self._texto_panel(
                surface, detalle, self._fuente_pequena, COLOR_SECUNDARIO,
                x, y, ancho, 2,
            )
            y += 2

        if self.nasa_error["neows"]:
            y = self._texto_panel(
                surface, self.nasa_error["neows"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 1,
            )
        return y

    def _seccion_apod(self, surface, x, y, ancho,
                      max_thumb_alto=None, max_explicacion=5):
        y = self._cabecera_panel(
            surface, "APOD · IMAGEN DEL DÍA", self._estado_capa("apod"),
            x, y, ancho, COLOR_ACENTO,
        )
        datos = self.nasa_datos.get("apod")

        if not datos and self.nasa_error["apod"]:
            y = self._texto_panel(
                surface, self.nasa_error["apod"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 2,
            )
            return self._texto_panel(
                surface, "Pulsa P para reintentar.", self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )

        if not datos:
            mensaje = ("Consultando APOD..." if self.nasa_cargando["apod"]
                       else "Sin datos de APOD.")
            return self._texto_panel(
                surface, mensaje, self._fuente_pequena, COLOR_SECUNDARIO,
                x, y, ancho, 1,
            )

        if self.apod_thumb is not None:
            miniatura = self.apod_thumb
            iw, ih = miniatura.get_size()
            if max_thumb_alto and ih > max_thumb_alto:
                escala = max_thumb_alto / ih
                miniatura = pygame.transform.smoothscale(
                    miniatura, (max(1, int(iw * escala)), max_thumb_alto)
                )
                iw, ih = miniatura.get_size()
            ix = x + max(0, (ancho - iw) // 2)
            surface.blit(miniatura, (ix, y))
            if datos.get("media_type") == "video":
                etiqueta = self._fuente_pequena.render("VIDEO", True, (5, 12, 22))
                fondo = pygame.Rect(
                    ix + 8, y + ih - 26, etiqueta.get_width() + 12, 18
                )
                pygame.draw.rect(surface, COLOR_ACENTO, fondo, border_radius=4)
                surface.blit(etiqueta, (fondo.x + 6, fondo.y + 2))
            y += ih + 6
        elif self.apod_thumb_cargando:
            y = self._texto_panel(
                surface, "Descargando imagen...", self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )
        elif self.apod_thumb_error:
            y = self._texto_panel(
                surface, self.apod_thumb_error, self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 1,
            )
        elif datos.get("media_type") == "image":
            y = self._texto_panel(
                surface, "Imagen no disponible.", self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )

        y = self._texto_panel(
            surface, datos.get("titulo", ""), self._fuente, COLOR_TEXTO,
            x, y, ancho, 2,
        )
        linea = datos.get("fecha", "")
        credito = datos.get("copyright") or ""
        if credito:
            linea = f"{linea} · {credito}" if linea else credito
        y = self._texto_panel(
            surface, linea, self._fuente_pequena, COLOR_SECUNDARIO,
            x, y, ancho, 1,
        )
        y = self._texto_panel(
            surface, datos.get("explicacion", ""), self._fuente_pequena,
            COLOR_TEXTO, x, y, ancho, max_explicacion,
        )

        if datos.get("media_type") == "video" and datos.get("url"):
            y = self._texto_panel(
                surface, "Vídeo: " + datos["url"], self._fuente_pequena,
                COLOR_SECUNDARIO, x, y, ancho, 1,
            )
        if self.nasa_error["apod"]:
            y = self._texto_panel(
                surface, self.nasa_error["apod"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 1,
            )
        return y

    def _seccion_controles(self, surface, x, y, ancho):
        pygame.draw.circle(surface, COLOR_ACENTO, (x + 4, y + 7), 4)
        surface.blit(
            self._fuente.render("CONTROLES", True, COLOR_TEXTO), (x + 14, y)
        )
        y += 24
        lineas = (
            "Arrastrar: rotar   ·   Rueda: zoom",
            "Clic: marcar / seleccionar",
            "Clic imagen satelital: ampliar",
            "E Eventos   A Asteroides   P APOD",
            "V EONET activos / históricos",
            "S Satélites NASA   ·   TLE en vivo",
            "G Retícula   N Noche   C Nubes",
            "Espacio Giro   R Reiniciar   ESC Salir",
        )
        for linea in lineas:
            surface.blit(
                self._fuente_pequena.render(linea, True, COLOR_SECUNDARIO),
                (x, y),
            )
            y += self._fuente_pequena.get_linesize()
        return y

    def _construir_panel_nasa(self, ancho):
        """Dibuja el panel lateral con cabecera fija y cuerpo desplazable."""
        ancho_int = ancho - 32
        fijo = pygame.Surface((ancho, max(260, self.alto)), pygame.SRCALPHA)
        x = 16
        y = 14

        fijo.blit(
            self._fuente_titulo.render("NASA · DATOS EN VIVO", True, COLOR_ACENTO),
            (x, y),
        )
        y += 27
        fijo.blit(
            self._fuente_pequena.render(
                "EONET · NEOWS · APOD · SATÉLITES · CONTROLES", True,
                COLOR_SECUNDARIO
            ),
            (x, y),
        )
        y += 20
        pygame.draw.line(fijo, (30, 55, 80), (x, y), (x + ancho_int, y))
        y += 12

        # Los controles van primero para que nunca queden fuera del panel.
        y = self._seccion_controles(fijo, x, y, ancho_int)
        pygame.draw.line(fijo, (30, 55, 80), (x, y), (x + ancho_int, y))
        y += 10
        body_top = y
        self._panel_body_top = body_top
        self._satelite_hitbox = None

        cuerpo = pygame.Surface(
            (ancho, max(1200, self.alto * 3)), pygame.SRCALPHA
        )
        yb = 0
        secciones = sum((
            bool(self.mostrar_eventos),
            bool(self.mostrar_asteroides),
            bool(self.mostrar_apod),
        ))
        compacto = self.alto < 940 and secciones >= 3
        max_objetos = 5 if self.alto >= 760 else 4
        if compacto:
            max_thumb = 96
        elif secciones == 2 and self.alto < 940:
            max_thumb = 150
        else:
            max_thumb = None
        max_explicacion = 3 if compacto else 5

        if self.mostrar_eventos:
            yb = self._seccion_eonet(cuerpo, x, yb, ancho_int)

        if self.mostrar_asteroides:
            if self.mostrar_eventos:
                pygame.draw.line(cuerpo, (30, 55, 80), (x, yb), (x + ancho_int, yb))
                yb += 10
            yb = self._seccion_neows(
                cuerpo, x, yb, ancho_int, max_objetos=max_objetos
            )

        if self.mostrar_apod:
            if self.mostrar_eventos or self.mostrar_asteroides:
                pygame.draw.line(cuerpo, (30, 55, 80), (x, yb), (x + ancho_int, yb))
                yb += 10
            yb = self._seccion_apod(
                cuerpo, x, yb, ancho_int,
                max_thumb_alto=max_thumb,
                max_explicacion=max_explicacion,
            )

        body_height = yb + 10 if yb else 0
        alto_max = max(80, self.alto - 40)
        alto = min(max(body_top + body_height, 60), alto_max)
        viewport = max(0, alto - body_top)
        scroll_max = max(0, body_height - viewport)
        self._panel_scroll_max = scroll_max
        self._panel_scroll = max(0, min(self._panel_scroll, scroll_max))

        panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.rect(panel, (5, 12, 22, 210), panel.get_rect(), border_radius=10)
        pygame.draw.rect(
            panel, (36, 66, 96, 150), panel.get_rect(), 1, border_radius=10
        )
        panel.blit(fijo, (0, 0), (0, 0, ancho, body_top))
        if viewport and body_height:
            visible = min(viewport, body_height - self._panel_scroll)
            if visible > 0:
                panel.blit(
                    cuerpo, (0, body_top),
                    (0, self._panel_scroll, ancho, visible),
                )

        if scroll_max > 0 and viewport > 8:
            track_x = ancho - 7
            track_y = body_top + 4
            track_h = max(1, viewport - 8)
            pygame.draw.rect(
                panel, (20, 35, 50), (track_x, track_y, 4, track_h),
                border_radius=2,
            )
            thumb_h = max(22, int(track_h * viewport / max(1, body_height)))
            thumb_y = track_y + int(
                (track_h - thumb_h) * self._panel_scroll / scroll_max
            )
            pygame.draw.rect(
                panel, (70, 145, 190), (track_x, thumb_y, 4, thumb_h),
                border_radius=2,
            )
        return panel

    def _dibujar_panel_nasa(self, pantalla):
        ancho = min(360, max(280, self.ancho - 40))
        clave = (
            self._nasa_version,
            self.ancho,
            self.alto,
            self.mostrar_eventos,
            self.mostrar_asteroides,
            self.mostrar_apod,
            self.eonet_modo,
            self._panel_scroll,
        )
        if self._nasa_panel is None or clave != self._nasa_panel_key:
            self._nasa_panel = self._construir_panel_nasa(ancho)
            self._nasa_panel_key = clave

        x = max(12, self.ancho - ancho - 22)
        y = 20
        self._nasa_panel_rect = pygame.Rect(
            x, y, ancho, self._nasa_panel.get_height()
        )
        pantalla.blit(self._nasa_panel, (x, y))

    def actualizar(self, dt):
        if self._enfocando:
            dif = (self._obj_yaw - self.yaw + math.pi) % (2.0 * math.pi) - math.pi
            paso = min(1.0, dt * 4.0)
            self.yaw += dif * paso
            self.pitch += (self._obj_pitch - self.pitch) * paso
            if abs(dif) < 0.002 and abs(self._obj_pitch - self.pitch) < 0.002:
                self.yaw = self._obj_yaw
                self.pitch = self._obj_pitch
                self._enfocando = False
        elif self.auto and not self._arrastrando:
            self.yaw -= self.vel_auto * dt

        self.zoom += (self.zoom_objetivo - self.zoom) * min(1.0, dt * 8.0)
        self._M = self._matriz()
        self._actualizar_sol()
        self._construir_geometria()
        if abs(self.zoom - self.zoom_objetivo) < 0.002 and self._halo_rp != self._r_pantalla:
            self._actualizar_halo()

        self._procesar_nasa()
        self._actualizar_nasa()
        self._actualizar_satelites()

    def dibujar(self, pantalla):
        pantalla.blit(self.estrellas, (0, 0))
        t = pygame.time.get_ticks() / 1000.0

        destino = self._renderizar_globo(t)
        if self._halo is not None and self._halo_rp == self._r_pantalla:
            media = self._halo.get_width() // 2
            cx, cy = self._centro()
            pantalla.blit(self._halo, (cx - media, cy - media), special_flags=pygame.BLEND_RGB_ADD)
        pantalla.blit(self._surf_final, destino)

        if self.mostrar_satelites:
            self._dibujar_orbita_satelite(pantalla)
        if self.mostrar_reticula:
            self._dibujar_reticula(pantalla)
        if self.mostrar_eventos:
            self._dibujar_eventos(pantalla)
        self._dibujar_marcador(pantalla)
        if self.mostrar_satelites:
            self._dibujar_satelites(pantalla)
        self._dibujar_hud(pantalla)
        self._dibujar_panel_nasa(pantalla)
        self._dibujar_panel_satelites(pantalla)
        self._dibujar_etiquetas_satelites(pantalla)
        self._dibujar_visor_satelite(pantalla)

    def manejar_evento(self, ev):
        if ev.type == pygame.QUIT:
            return False

        if self.visor_satelite_abierto:
            return self._manejar_evento_visor(ev)

        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                return False
            if ev.key == pygame.K_SPACE:
                self.auto = not self.auto
                self._enfocando = False
            elif ev.key == pygame.K_g:
                self.mostrar_reticula = not self.mostrar_reticula
            elif ev.key == pygame.K_n:
                self.mostrar_noche = not self.mostrar_noche
            elif ev.key == pygame.K_c:
                self.mostrar_nubes = not self.mostrar_nubes
            elif ev.key == pygame.K_e:
                self._alternar_capa("eonet")
            elif ev.key == pygame.K_a:
                self._alternar_capa("neows")
            elif ev.key == pygame.K_p:
                self._alternar_capa("apod")
            elif ev.key == pygame.K_s:
                self._alternar_capa("satelites")
            elif ev.key == pygame.K_v:
                self._alternar_modo_eonet()
            elif ev.key == pygame.K_r:
                self.reiniciar()
            elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.zoom_objetivo = min(ZOOM_MAX, self.zoom_objetivo * 1.12)
            elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.zoom_objetivo = max(ZOOM_MIN, self.zoom_objetivo / 1.12)

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if (ev.button == 1 and self.mostrar_satelites
                    and self._satelites_panel_rect.collidepoint(ev.pos)):
                self._click_panel = True
                self._arrastrando = False
                catnr = self._catnr_fila(ev.pos)
                if catnr is not None:
                    self.satelite_sel_catnr = (
                        None if self.satelite_sel_catnr == catnr else catnr
                    )
                return True
            if (ev.button in (1, 3)
                    and self._nasa_panel_rect.collidepoint(ev.pos)):
                if ev.button == 1:
                    self._click_panel = True
                self._arrastrando = False
                self._intentar_abrir_visor(ev.pos, ev.button)
                return True
            if ev.button == 1:
                self._click_panel = False
                self._arrastrando = True
                self._click_pos = ev.pos
                self._movido = 0.0
                self.auto = False
                self._enfocando = False

        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button in (1, 3) and self._click_panel:
                self._click_panel = False
                self._click_pos = None
                return True
            if ev.button == 1:
                self._arrastrando = False
                if self._click_pos is not None and self._movido < 6.0:
                    satelite = (
                        self._satelite_cercano(*self._click_pos)
                        if (self.mostrar_satelites
                            and not self._hud_rect.collidepoint(self._click_pos))
                        else None
                    )
                    if satelite is not None:
                        catnr = satelite["sat"].get("catnr")
                        self.satelite_sel_catnr = (
                            None if self.satelite_sel_catnr == catnr else catnr
                        )
                        self._click_pos = None
                        return True
                    evento = self._evento_cercano(*self._click_pos)
                    if evento is not None:
                        self.satelite_sel_catnr = None
                        self.evento_sel = evento
                        self.marcar(evento["lat"], evento["lon"])
                        self._panel_scroll = 0
                        self._solicitar_satelite()
                        self._nasa_version += 1
                    else:
                        if self.evento_sel is not None:
                            self.evento_sel = None
                            self._solicitar_satelite()
                            self._nasa_version += 1
                        self.satelite_sel_catnr = None
                        coord = self.coordenadas_en(*self._click_pos)
                        if coord is not None:
                            self.marcar(*coord)
                self._click_pos = None

        elif ev.type == pygame.MOUSEMOTION and self._arrastrando:
            dx, dy = ev.rel
            self._movido += abs(dx) + abs(dy)
            self.yaw += dx * 0.005
            self.pitch = max(math.radians(-85.0), min(math.radians(85.0),
                                                      self.pitch + dy * 0.005))

        elif ev.type == pygame.MOUSEWHEEL:
            if (self.mostrar_satelites
                    and self._satelites_panel_rect.collidepoint(
                        pygame.mouse.get_pos()
                    )):
                return True
            if self._nasa_panel_rect.collidepoint(pygame.mouse.get_pos()):
                if self._panel_scroll_max > 0:
                    nuevo = max(
                        0,
                        min(
                            self._panel_scroll_max,
                            self._panel_scroll - ev.y * 36,
                        ),
                    )
                    if nuevo != self._panel_scroll:
                        self._panel_scroll = nuevo
                        self._nasa_version += 1
                return True
            self.zoom_objetivo = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom_objetivo * (1.12 ** ev.y)))

        return True

    def redimensionar(self, ancho, alto):
        self.ancho = max(480, ancho)
        self.alto = max(360, alto)
        self._panel_scroll = 0
        self._satelites_panel_rect = pygame.Rect(0, 0, 0, 0)
        self._satelites_filas = []
        self.visor_satelite_rect = pygame.Rect(0, 0, 0, 0)
        self._visor_rects = {}
        self._visor_cache_key = None
        self._visor_cache = None
        self._crear_estrellas()
        self._r = -1
        self._construir_geometria()
        self._actualizar_halo()

    def reiniciar(self):
        self.yaw = math.radians(-40.0)
        self.pitch = math.radians(16.0)
        self.zoom_objetivo = 1.0
        self.auto = True
        self._enfocando = False
        self.marcador = None
        self.evento_sel = None
        self.satelite_sel_catnr = None
        self.satelite_hover_catnr = None
        self._panel_scroll = 0
        self._cerrar_visor_satelite()
        self._nasa_version += 1

    def cerrar(self):
        self._cerrar_visor_satelite()
        self.nasa.cerrar()
        self.rastreador.cerrar()

    def enfocar(self, lat, lon, zoom=None):
        self._obj_yaw = math.radians(-lon)
        self._obj_pitch = math.radians(lat)
        self._enfocando = True
        self.auto = False
        if zoom is not None:
            self.zoom_objetivo = max(ZOOM_MIN, min(ZOOM_MAX, zoom))

    def marcar(self, lat, lon=None):
        if lat is None:
            self.marcador = None
        else:
            self.marcador = (lat, lon)


def main():
    pygame.init()
    pygame.display.set_caption("Tierra · NASA Monitor")
    pantalla = pygame.display.set_mode((ANCHO, ALTO), pygame.RESIZABLE)
    tierra = Tierra(ANCHO, ALTO)
    reloj = pygame.time.Clock()
    ejecutando = True

    while ejecutando:
        dt = min(reloj.tick(FPS) / 1000.0, 0.05)
        tierra.fps = reloj.get_fps()
        for ev in pygame.event.get():
            if ev.type == pygame.VIDEORESIZE:
                nuevo = (max(480, ev.w), max(360, ev.h))
                pantalla = pygame.display.set_mode(nuevo, pygame.RESIZABLE)
                tierra.redimensionar(*nuevo)
            elif not tierra.manejar_evento(ev):
                ejecutando = False

        tierra.actualizar(dt)
        tierra.dibujar(pantalla)
        pygame.display.flip()

    tierra.cerrar()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
