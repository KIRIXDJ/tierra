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
        self.assertGreaterEqual(color[3], 100)
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
        self.assertLessEqual(color[3], 60)  # no significativa, tenue
        pag.evaluate("window.__tierra.estado.soloSignificativas = true; window.__tierra.repintar()")
        color = pag.evaluate(f"window.__tierra.colorCelda({amazonia})")
        self.assertEqual(color[3], 0)
        color = pag.evaluate(f"window.__tierra.colorCelda({idx})")
        self.assertEqual(color[3], 0)

    def test_panel_con_serie(self):
        import json
        pag = self.nav.new_page()
        fixture = json.loads(Path("tests/fixtures/power_serie.json").read_text(encoding="utf-8"))
        pag.route("**/power.larc.nasa.gov/**", lambda r: r.fulfill(status=200, json=fixture))
        pag.goto(html_de_prueba(Path("tests") / "_tmp_panel.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.evaluate("window.__tierra.seleccionar(17.5, -72.5)")
        pag.wait_for_function(
            "document.querySelector('#panel-pendiente').textContent.includes('°C/década')",
            timeout=15000)
        self.assertIn("Significativo", pag.inner_text("#panel-insignia"))
        self.assertGreater(pag.evaluate("document.querySelector('#panel-serie').width"), 100)

    def test_celda_sin_dato(self):
        pag = self.nav.new_page()
        pag.goto(html_de_prueba(Path("tests") / "_tmp_sindato.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.evaluate("window.__tierra.cambiarVariable('PRECTOTCORR')")
        pag.evaluate("window.__tierra.seleccionar(77.5, 17.5)")
        pag.wait_for_selector("#panel.visible")
        self.assertIn("Sin datos", pag.inner_text("#panel-insignia"))

    def test_capas_eventos(self):
        pag = self.nav.new_page()
        pag.goto(html_de_prueba(Path("tests") / "_tmp_capas.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.evaluate("window.__tierra.alternarCapa('incendios')")
        self.assertTrue(pag.evaluate("window.__tierra.capas.incendios"))
        self.assertGreater(pag.evaluate("window.__tierra.puntosIncendios()"), 0)
        pag.evaluate("window.__tierra.seleccionar(17.5, -72.5)")
        pag.wait_for_selector("#panel.visible")
        self.assertIn("incendios", pag.inner_text("#panel-eventos"))

    def test_modo_manos(self):
        ctx = self.nav.new_context(permissions=["camera"])
        pag = ctx.new_page()
        pag.goto(html_de_prueba(Path("tests") / "_tmp_manos.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.click("#manos-boton")
        pag.wait_for_function("window.__manos && window.__manos.activo", timeout=40000)
        mano = [[0.5, 0.7, 0.0] for _ in range(21)]
        mano[0] = [0.5, 0.7, 0.0]
        mano[9] = [0.5, 0.55, 0.0]
        mano[4] = [0.50, 0.50, 0.0]
        mano[8] = [0.51, 0.51, 0.0]
        pag.evaluate("(m) => window.__manos.simular([m])", mano)
        self.assertEqual(pag.evaluate("window.__manos.gesto"), "pinch")
        self.assertEqual(pag.inner_text("#manos-estado").lower(), "pinza")
        ctx.close()

    def test_camara_denegada(self):
        pag = self.nav.new_page()
        pag.add_init_script(
            "navigator.mediaDevices.getUserMedia = "
            "() => Promise.reject(new DOMException('denegado', 'NotAllowedError'))")
        pag.goto(html_de_prueba(Path("tests") / "_tmp_manos2.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.click("#manos-boton")
        pag.wait_for_selector("#manos-aviso.visible", timeout=15000)
        self.assertFalse(pag.evaluate("window.__manos.activo"))
        self.assertIn("cámara", pag.inner_text("#manos-aviso"))

    def test_error_de_red_y_escape(self):
        pag = self.nav.new_page()
        pag.route("**/power.larc.nasa.gov/**", lambda r: r.abort())
        pag.goto(html_de_prueba(Path("tests") / "_tmp_error.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        pag.evaluate("window.__tierra.seleccionar(17.5, -72.5)")
        pag.wait_for_selector("#panel-error.visible", timeout=15000)
        self.assertIn("No pudimos", pag.inner_text("#panel-error"))
        pag.keyboard.press("Escape")
        self.assertFalse(pag.evaluate("document.querySelector('#panel').classList.contains('visible')"))

    def test_sin_desbordamiento(self):
        pag = self.nav.new_page(viewport={"width": 1366, "height": 768})
        pag.goto(html_de_prueba(Path("tests") / "_tmp_resp.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo")
        self.assertLessEqual(
            pag.evaluate("document.scrollingElement.scrollWidth"),
            pag.evaluate("window.innerWidth"))

    def test_texturas_caidas(self):
        pag = self.nav.new_page()
        pag.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
        pag.goto(html_de_prueba(Path("tests") / "_tmp_sintex.html"))
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=30000)
        self.assertFalse(pag.evaluate("window.__tierra.globo.texturas.ok"))
        self.assertTrue(pag.evaluate("window.__tierra.globo.escena.children.length > 0"))
