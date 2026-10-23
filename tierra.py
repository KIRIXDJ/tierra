import io
import math
import os
import sys
import time

import numpy as np
import pygame
import pygame.surfarray as surfarray

try:
    from nasa_service import NasaService
except ImportError:
    from .nasa_service import NasaService


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
COLOR_EVENTO_DEFECTO = (200, 200, 200)

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
COOLDOWN_NASA = 60.0


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

        self.mostrar_eventos = False
        self.mostrar_asteroides = False
        self.mostrar_apod = False

        self.eventos = []
        self._eventos_xyz = np.empty((0, 3), dtype=np.float32)
        self._eventos_colores = []
        self.evento_sel = None

        self.apod_thumb = None
        self.apod_thumb_cargando = False
        self.apod_thumb_error = None
        self._apod_imagen_url_intentada = None
        self._apod_imagen_fallida = None

        self._nasa_version = 0
        self._nasa_panel = None
        self._nasa_panel_key = None
        self._nasa_panel_rect = pygame.Rect(0, 0, 0, 0)
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
        self.eventos = eventos or []
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

        self._nasa_version += 1

    def _dibujar_eventos(self, pantalla):
        """Pinta un punto por cada evento EONET visible en la cara del globo."""
        if not self.mostrar_eventos or not self.eventos:
            return

        scr = self._eventos_xyz @ self._M
        visibles = scr[:, 2] > 0.02
        if not np.any(visibles):
            return

        cx, cy = self._centro()
        radio = self._r_pantalla
        for indice in np.flatnonzero(visibles):
            x = int(cx + scr[indice, 0] * radio)
            y = int(cy - scr[indice, 1] * radio)
            pygame.draw.circle(pantalla, (8, 18, 28), (x, y), 5)
            pygame.draw.circle(pantalla, self._eventos_colores[indice], (x, y), 3)

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

        rect = pygame.Rect(22, 20, 340, 122)
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

        if self.marcador is not None:
            mlat, mlon = self.marcador
            texto_marca = (f"MARCADOR  {abs(mlat):.2f}°{'N' if mlat >= 0 else 'S'}"
                           f"   {abs(mlon):.2f}°{'E' if mlon >= 0 else 'O'}")
            color_marca = COLOR_MARCADOR
        else:
            texto_marca = "CLIC EN EL GLOBO PARA MARCAR UN PUNTO"
            color_marca = COLOR_SECUNDARIO
        pantalla.blit(self._fuente_pequena.render(texto_marca, True, color_marca),
                      (rect.x + 16, rect.y + 96))

        ayudas = "Arrastrar: rotar   ·   Rueda: zoom   ·   Clic: marcar/seleccionar   ·   Espacio: giro"
        pantalla.blit(self._fuente_pequena.render(ayudas, True, COLOR_SECUNDARIO), (22, self.alto - 46))
        ayudas2 = "G: retícula  ·  N: noche  ·  C: nubes  ·  E: eventos  ·  A: asteroides  ·  P: APOD  ·  R: reiniciar  ·  ESC: salir"
        pantalla.blit(self._fuente_pequena.render(ayudas2, True, COLOR_SECUNDARIO), (22, self.alto - 28))

    def _panel_nasa_activo(self):
        return self.mostrar_eventos or self.mostrar_asteroides or self.mostrar_apod

    def _estado_capa(self, tipo):
        if self.nasa_cargando.get(tipo):
            return "CARGANDO"
        if self.nasa_error.get(tipo):
            return "ERROR"
        ts = self.nasa_ts.get(tipo, 0.0)
        return "ACT. " + time.strftime("%H:%M", time.localtime(ts)) if ts else ""

    def _solicitar_nasa(self, tipo, forzar=False):
        """Pide datos a NASA respetando caché, clave y peticiones en curso."""
        ahora = time.time()
        datos = self.nasa_datos.get(tipo)

        if (not forzar and datos is not None
                and ahora - self.nasa_ts.get(tipo, 0.0) < TTL_NASA[tipo]):
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
            return

        if self.nasa.solicitar(tipo):
            self.nasa_cargando[tipo] = True
            self.nasa_error[tipo] = None
            self.nasa_intento[tipo] = ahora
            self._nasa_version += 1

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

            self.nasa_cargando[tipo] = False
            if error:
                self.nasa_error[tipo] = error
                self._nasa_version += 1
                continue

            if tipo == "eonet":
                self.nasa_datos[tipo] = datos or []
                self.nasa_ts[tipo] = time.time()
                self.nasa_error[tipo] = None
                self._cargar_eventos(self.nasa_datos[tipo])
            elif tipo == "neows":
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

            datos = self.nasa_datos.get(tipo)
            if datos is None or ahora - self.nasa_ts[tipo] >= TTL_NASA[tipo]:
                self._solicitar_nasa(tipo)

    def _alternar_capa(self, tipo):
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
                surface, "Sin eventos activos en los últimos 7 días.",
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
            surface, f"{len(self.eventos)} eventos activos · 7 días",
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
        return self._texto_panel(
            surface, f"{etiqueta} · {evento.get('fecha') or 'sin fecha'}",
            self._fuente_pequena, color, x, y, ancho, 1,
        )

    def _seccion_neows(self, surface, x, y, ancho):
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
            f"{datos.get('total', 0)} NEOs · 7 días · LD / km/s / Ø km",
            self._fuente_pequena, COLOR_TEXTO, x, y, ancho, 1,
        )

        for objeto in datos.get("objetos", []):
            nombre = self._recortar(
                objeto.get("nombre", ""), self._fuente_pequena, ancho - 34
            )
            surface.blit(
                self._fuente_pequena.render(nombre, True, COLOR_TEXTO), (x, y)
            )
            if objeto.get("peligroso"):
                pha = self._fuente_pequena.render("PHA", True, COLOR_ALERTA)
                surface.blit(pha, (x + ancho - pha.get_width(), y))
            y += self._fuente_pequena.get_linesize()

            fecha = objeto.get("fecha") or ""
            corta = fecha[5:10] if len(fecha) >= 10 else "—"
            ld = (f"{objeto['distancia_ld']:.1f}"
                  if objeto.get("distancia_ld") is not None else "—")
            velocidad = (f"{objeto['velocidad_kms']:.1f}"
                         if objeto.get("velocidad_kms") is not None else "—")
            dmin = (f"{objeto['diametro_min_km']:.2f}"
                    if objeto.get("diametro_min_km") is not None else "—")
            dmax = (f"{objeto['diametro_max_km']:.2f}"
                    if objeto.get("diametro_max_km") is not None else "—")
            detalle = f"{corta} · {ld} LD · {velocidad} km/s · {dmin}-{dmax}"
            y = self._texto_panel(
                surface, detalle, self._fuente_pequena, COLOR_SECUNDARIO,
                x, y, ancho, 1,
            )
            y += 2

        if self.nasa_error["neows"]:
            y = self._texto_panel(
                surface, self.nasa_error["neows"], self._fuente_pequena,
                COLOR_ALERTA, x, y, ancho, 1,
            )
        return y

    def _seccion_apod(self, surface, x, y, ancho):
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
            iw, ih = self.apod_thumb.get_size()
            ix = x + max(0, (ancho - iw) // 2)
            surface.blit(self.apod_thumb, (ix, y))
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
            COLOR_TEXTO, x, y, ancho, 5,
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

    def _construir_panel_nasa(self, ancho):
        """Dibuja el panel lateral en una superficie y la devuelve cacheada."""
        contenido = pygame.Surface((ancho, max(300, self.alto)), pygame.SRCALPHA)
        x = 16
        y = 14
        ancho_int = ancho - 32

        contenido.blit(
            self._fuente_titulo.render("NASA · DATOS EN VIVO", True, COLOR_ACENTO),
            (x, y),
        )
        y += 27
        contenido.blit(
            self._fuente_pequena.render("EONET · NEOWS · APOD", True, COLOR_SECUNDARIO),
            (x, y),
        )
        y += 20
        pygame.draw.line(contenido, (30, 55, 80), (x, y), (x + ancho_int, y))
        y += 12

        if self.mostrar_eventos:
            y = self._seccion_eonet(contenido, x, y, ancho_int)

        if self.mostrar_asteroides:
            if self.mostrar_eventos:
                pygame.draw.line(
                    contenido, (30, 55, 80), (x, y), (x + ancho_int, y)
                )
                y += 10
            y = self._seccion_neows(contenido, x, y, ancho_int)

        if self.mostrar_apod:
            if self.mostrar_eventos or self.mostrar_asteroides:
                pygame.draw.line(
                    contenido, (30, 55, 80), (x, y), (x + ancho_int, y)
                )
                y += 10
            y = self._seccion_apod(contenido, x, y, ancho_int)

        alto_max = max(80, self.alto - 90)
        alto = min(contenido.get_height(), max(60, y + 10), alto_max)
        panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.rect(panel, (5, 12, 22, 210), panel.get_rect(), border_radius=10)
        pygame.draw.rect(
            panel, (36, 66, 96, 150), panel.get_rect(), 1, border_radius=10
        )
        panel.blit(contenido, (0, 0), (0, 0, ancho, alto))
        return panel

    def _dibujar_panel_nasa(self, pantalla):
        if not self._panel_nasa_activo():
            self._nasa_panel_rect = pygame.Rect(0, 0, 0, 0)
            return

        ancho = min(360, max(280, self.ancho - 40))
        clave = (
            self._nasa_version,
            self.ancho,
            self.alto,
            self.mostrar_eventos,
            self.mostrar_asteroides,
            self.mostrar_apod,
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
        self._construir_geometria()
        if abs(self.zoom - self.zoom_objetivo) < 0.002 and self._halo_rp != self._r_pantalla:
            self._actualizar_halo()

        self._procesar_nasa()
        self._actualizar_nasa()

    def dibujar(self, pantalla):
        pantalla.blit(self.estrellas, (0, 0))
        t = pygame.time.get_ticks() / 1000.0

        destino = self._renderizar_globo(t)
        if self._halo is not None and self._halo_rp == self._r_pantalla:
            media = self._halo.get_width() // 2
            cx, cy = self._centro()
            pantalla.blit(self._halo, (cx - media, cy - media), special_flags=pygame.BLEND_RGB_ADD)
        pantalla.blit(self._surf_final, destino)

        if self.mostrar_reticula:
            self._dibujar_reticula(pantalla)
        if self.mostrar_eventos:
            self._dibujar_eventos(pantalla)
        self._dibujar_marcador(pantalla)
        self._dibujar_hud(pantalla)
        self._dibujar_panel_nasa(pantalla)

    def manejar_evento(self, ev):
        if ev.type == pygame.QUIT:
            return False

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
            elif ev.key == pygame.K_r:
                self.reiniciar()
            elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.zoom_objetivo = min(ZOOM_MAX, self.zoom_objetivo * 1.12)
            elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.zoom_objetivo = max(ZOOM_MIN, self.zoom_objetivo / 1.12)

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                if self._nasa_panel_rect.collidepoint(ev.pos):
                    self._click_panel = True
                    self._arrastrando = False
                    return True
                self._click_panel = False
                self._arrastrando = True
                self._click_pos = ev.pos
                self._movido = 0.0
                self.auto = False
                self._enfocando = False

        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                if self._click_panel:
                    self._click_panel = False
                    self._click_pos = None
                    return True
                self._arrastrando = False
                if self._click_pos is not None and self._movido < 6.0:
                    evento = self._evento_cercano(*self._click_pos)
                    if evento is not None:
                        self.evento_sel = evento
                        self.marcar(evento["lat"], evento["lon"])
                        self._nasa_version += 1
                    else:
                        if self.evento_sel is not None:
                            self.evento_sel = None
                            self._nasa_version += 1
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
            if self._nasa_panel_rect.collidepoint(pygame.mouse.get_pos()):
                return True
            self.zoom_objetivo = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom_objetivo * (1.12 ** ev.y)))

        return True

    def redimensionar(self, ancho, alto):
        self.ancho = max(480, ancho)
        self.alto = max(360, alto)
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
        self._nasa_version += 1

    def cerrar(self):
        self.nasa.cerrar()

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
