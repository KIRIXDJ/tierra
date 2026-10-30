import unittest
from tools.html_malla import leer_malla, reemplazar_malla

HTML = '<html><script id="malla" type="application/json">{"version": 1}</script></html>'


class TestHtmlMalla(unittest.TestCase):
    def test_leer(self):
        self.assertEqual(leer_malla(HTML), {"version": 1})

    def test_reemplazar(self):
        nuevo = reemplazar_malla(HTML, {"version": 2, "celdas": []})
        self.assertEqual(leer_malla(nuevo), {"version": 2, "celdas": []})
        self.assertIn('id="malla"', nuevo)

    def test_sin_bloque(self):
        with self.assertRaises(ValueError):
            leer_malla("<html></html>")
