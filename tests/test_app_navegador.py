"""Prueba de humo de la app real en un navegador.

Abre ``web/index.html`` servido por http, espera a que el globo esté listo y
recorre las pestañas. Es el test que evita que la demo se rompa sin avisar.
Necesita playwright y un navegador: si no están, se salta.
"""

import functools
import http.server
import pathlib
import socketserver
import threading
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise unittest.SkipTest("requiere playwright (pip install playwright)")


class Servidor:
    def __enter__(self):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ))
        socketserver.TCPServer.allow_reuse_address = True
        self.servidor = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.puerto}"

    def __exit__(self, *exc):
        self.servidor.shutdown()
        return False


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        try:
            cls.nav = cls._pw.chromium.launch(headless=True)
        except Exception:
            cls._pw.stop()
            raise unittest.SkipTest("requiere un navegador de playwright")
        cls.servidor = Servidor()
        cls.base = cls.servidor.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.__exit__(None, None, None)
        cls.nav.close()
        cls._pw.stop()

    def abrir(self):
        pag = self.nav.new_page(viewport={"width": 1366, "height": 768})
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=45000)
        return pag, errores

    def test_globo_sin_cdn(self):
        pag, errores = self.abrir()
        self.assertTrue(pag.evaluate("window.__tierra.globo.texturas.ok"),
                        "las texturas locales no cargaron")
        self.assertEqual(errores, [])
        pag.close()

    def test_pestana_finca(self):
        pag, errores = self.abrir()
        pag.click("#finca-boton")
        pag.wait_for_selector("#finca.visible")
        filas = pag.inner_text("#finca-filas")
        self.assertIn("Lluvia 30 d", filas)
        self.assertIn("Humedad superficial", filas)
        self.assertIn("Suelo", filas)
        self.assertIn("Open-Meteo", pag.inner_text("#finca-pie"))
        self.assertIn("no NASA", pag.inner_text("#finca-pie"))
        self.assertIn("no mezclar", pag.inner_text("#finca-avisos").lower()
                      .replace("mezclar", "mezclar"))
        self.assertEqual(errores, [])
        pag.close()

    def test_pestana_rotaciones(self):
        pag, errores = self.abrir()
        pag.click("#rotaciones-boton")
        pag.wait_for_selector("#rotaciones.visible")
        tarjetas = pag.eval_on_selector_all(".tarjeta", "e => e.length")
        self.assertEqual(tarjetas, 3)
        self.assertIn("NASA", pag.inner_text(".tarjeta"))
        rotulos = pag.eval_on_selector_all(".tarjeta:nth-child(1) .rotulo",
                                           "e => e.map(x => x.textContent)")
        for esperado in ("Por qué se sugiere", "Beneficios", "Qué datos faltan",
                         "Revisar con un agrónomo"):
            self.assertIn(esperado, rotulos)
        # El escenario de sequía baja el índice de la estrategia con peor agua.
        antes = pag.eval_on_selector_all(".tarjeta .indice", "e => e.map(x => x.textContent)")
        pag.fill("#escenario-lluvia", "-40")
        pag.dispatch_event("#escenario-lluvia", "input")
        despues = pag.eval_on_selector_all(".tarjeta .indice", "e => e.map(x => x.textContent)")
        self.assertNotEqual(antes, despues)
        self.assertEqual(errores, [])
        pag.close()

    def test_metodo_y_elio(self):
        pag, errores = self.abrir()
        pag.click("#metodo-boton")
        pag.wait_for_selector("#metodo.visible")
        texto = pag.inner_text("#metodo")
        self.assertIn("reanálisis", texto)
        self.assertIn("agrónomo", texto)
        self.assertIn("Satélite, modelo y terreno", texto)
        pag.click("#elio-boton")
        pag.wait_for_selector("#elio.visible")
        pag.fill("#elio-pregunta", "activa el riego")
        pag.click("#elio-enviar")
        self.assertIn("No controlo dispositivos", pag.inner_text("#elio-respuesta"))
        pag.fill("#elio-pregunta", "¿cuánta lluvia?")
        pag.click("#elio-enviar")
        self.assertIn("Open-Meteo", pag.inner_text("#elio-respuesta"))
        self.assertEqual(errores, [])
        pag.close()


if __name__ == "__main__":
    unittest.main()
