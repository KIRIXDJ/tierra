import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.apoyo import html_de_prueba


class TestGlobo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        cls.nav = cls._pw.chromium.launch(
            channel="chrome", headless=True,
            args=["--use-fake-device-for-media-stream",
                  "--use-fake-ui-for-media-stream"],
        )

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls._pw.stop()

    def test_carga_y_dibuja(self):
        pag = self.nav.new_page()
        errores = []
        pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pag.goto(html_de_prueba(Path("tests") / "_tmp_globo.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=30000)
        self.assertEqual(pag.evaluate("window.__tierra.estado.variable"), "T2M")
        self.assertGreater(pag.evaluate("window.__tierra.globo.escena.children.length"), 3)
        self.assertEqual(errores, [])
        pag.close()

    def test_malla_y_variables(self):
        pag = self.nav.new_page()
        pag.goto(html_de_prueba(Path("tests") / "_tmp_malla.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        self.assertEqual(pag.evaluate("window.__tierra.datos.celdas.length"), 4)
        idx = pag.evaluate("window.__tierra.indiceCelda(18.9, -70.7)")
        self.assertGreaterEqual(idx, 0)
        color = pag.evaluate(f"window.__tierra.colorCelda({idx})")
        self.assertEqual(color[3], 255)
        pag.evaluate("window.__tierra.cambiarVariable('PRECTOTCORR')")
        self.assertEqual(pag.evaluate("window.__tierra.estado.variable"), "PRECTOTCORR")
        self.assertIn("Lluvia", pag.inner_text("#leyenda"))

    def test_bordes_y_sin_dato(self):
        pag = self.nav.new_page()
        pag.goto(html_de_prueba(Path("tests") / "_tmp_malla2.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        self.assertEqual(pag.evaluate("window.__tierra.indiceCelda(89.9, 180)"),
                         pag.evaluate("window.__tierra.indiceCelda(87.5, -180)"))
        pag.evaluate("window.__tierra.cambiarVariable('PRECTOTCORR')")
        idx = pag.evaluate("window.__tierra.indiceCelda(78.9, 15.1)")
        color = pag.evaluate(f"window.__tierra.colorCelda({idx})")
        self.assertEqual(color[:3], [128, 128, 128])
        amazonia = pag.evaluate("window.__tierra.indiceCelda(-3, -62)")
        color = pag.evaluate(f"window.__tierra.colorCelda({amazonia})")
        self.assertEqual(color[3], 77)  # no significativa al 30 %
        pag.evaluate("window.__tierra.estado.soloSignificativas = true; window.__tierra.repintar()")
        color = pag.evaluate(f"window.__tierra.colorCelda({amazonia})")
        self.assertEqual(color[3], 0)
        color = pag.evaluate(f"window.__tierra.colorCelda({idx})")
        self.assertEqual(color[3], 0)
