"""El globo debe pintarse sin depender de un CDN: si el wifi del lugar falla,
la demo no puede quedarse en negro."""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")


class TestSinCdn(unittest.TestCase):
    def test_three_es_local(self):
        """three.js pinta el globo: tiene que ser local, sin CDN."""
        importmap = re.search(r'<script type="importmap">(.*?)</script>', HTML, re.S).group(1)
        self.assertIn("./vendor/three.module.js", importmap)
        entrada = re.search(r'"three":\s*"([^"]+)"', importmap).group(1)
        self.assertFalse(entrada.startswith("http"), f"three debe ser local: {entrada}")

    def test_vendor_existe(self):
        for ruta in ("web/vendor/three.module.js", "web/vendor/three.core.js",
                     "web/vendor/addons/controls/OrbitControls.js"):
            self.assertTrue((RAIZ / ruta).is_file(), f"falta {ruta}")

    def test_texturas_locales(self):
        self.assertNotIn("raw.githubusercontent.com", HTML)
        self.assertIn("const TEXTURAS = '../textures/'", HTML)
        for nombre in re.findall(r"cargarTextura\('([^']+)'\)", HTML):
            self.assertTrue((RAIZ / "textures" / nombre).is_file(), f"falta textures/{nombre}")

    def test_solo_datos_nasa_en_vivo(self):
        """Las llamadas externas que quedan son APIs de datos, no librerías."""
        externas = set(re.findall(r"https://([a-z0-9.-]+)/", HTML))
        permitidas = {"power.larc.nasa.gov", "wvs.earthdata.nasa.gov",
                      "eonet.gsfc.nasa.gov", "archive-api.open-meteo.com",
                      "storage.googleapis.com", "cdn.jsdelivr.net"}
        self.assertTrue(externas <= permitidas, f"dominios nuevos: {externas - permitidas}")
        self.assertNotIn("cdn.jsdelivr.net", HTML)
        self.assertNotIn("mediapipe", HTML.lower())


if __name__ == "__main__":
    unittest.main()
