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
