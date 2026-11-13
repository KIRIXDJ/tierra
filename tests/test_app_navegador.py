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
            cls.nav = cls._pw.chromium.launch(headless=True, args=["--use-fake-device-for-media-stream",
                      "--use-fake-ui-for-media-stream",
                      # Sin GPU en el CI: render por software para que WebGL exista.
                      "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
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
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
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
        # La comparación de las tres estrategias, en una tabla.
        cabeceras = pag.eval_on_selector_all("#rotaciones-tabla th",
                                            "e => e.map(x => x.textContent)")
        self.assertEqual(cabeceras, ["Plan", "Índice", "Demanda", "Secos", "Provisional"])
        self.assertEqual(pag.eval_on_selector_all("#rotaciones-tabla tbody tr", "e => e.length"), 3)
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

    def test_movil_no_desborda(self):
        """El agricultor lo abre en el teléfono: el panel debe entrar entero."""
        pag = self.nav.new_page(viewport={"width": 390, "height": 844},
                                is_mobile=True, has_touch=True)
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        pag.click("#finca-boton")
        pag.wait_for_selector("#finca.visible")
        caja = pag.evaluate("""() => {
            const d = document.getElementById('finca').getBoundingClientRect();
            return { x: Math.round(d.x), w: Math.round(d.width),
                     desborda: d.right > window.innerWidth || d.x < 0 };
        }""")
        self.assertFalse(caja["desborda"], f"el panel se sale: {caja}")
        self.assertGreater(caja["w"], 300)
        pag.close()

    def test_sin_internet_los_paneles_funcionan(self):
        """Plan B de la feria: aunque falle el wifi, los paneles deben responder.

        Se bloquea toda la red externa (solo se sirve lo local) y se recorre la
        pestaña Finca, la de Rotaciones y Elio.
        """
        pag = self.nav.new_page(viewport={"width": 1366, "height": 768})
        externas = []

        def filtrar(route):
            url = route.request.url
            if "127.0.0.1" in url or url.startswith(("data:", "blob:")):
                route.continue_()
            else:
                externas.append(url)
                route.abort()

        pag.route("**/*", filtrar)
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)

        pag.click("#finca-boton")
        pag.wait_for_selector("#finca.visible")
        self.assertIn("Lluvia 30 d", pag.inner_text("#finca-filas"))

        pag.click("#rotaciones-boton")
        pag.wait_for_selector("#rotaciones.visible")
        self.assertEqual(pag.eval_on_selector_all(".tarjeta", "e => e.length"), 3)

        pag.click("#elio-boton")
        pag.wait_for_selector("#elio.visible")
        pag.fill("#elio-pregunta", "¿cómo va la temporada?")
        pag.click("#elio-enviar")
        respuesta = pag.inner_text("#elio-respuesta")
        self.assertTrue(respuesta.strip())
        self.assertNotIn("No tengo ese dato", respuesta)

        self.assertEqual(errores, [], "errores de JS con la red caída")
        pag.close()

    def test_granja_conectada_es_simulacion(self):
        """La vista de producto debe decir que es simulada y reaccionar."""
        pag = self.nav.new_page(viewport={"width": 1366, "height": 768})
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        aviso = pag.inner_text(".simulacion")
        self.assertIn("Vista simulada", aviso)
        self.assertIn("No hay hardware conectado", aviso)
        # Con humedad baja riega; con lluvia cierra el techo y suspende el riego.
        pag.fill("#vision-humedad", "8")
        pag.dispatch_event("#vision-humedad", "input")
        self.assertIn("3", pag.inner_text("#vision-resumen"))
        pag.fill("#vision-lluvia", "4")
        pag.dispatch_event("#vision-lluvia", "input")
        resumen = pag.inner_text("#vision-resumen")
        self.assertIn("techos cerrados", resumen)
        pag.click("#vision-telegram")
        self.assertIn("[", pag.inner_text("#vision-log"))
        self.assertEqual(errores, [])
        pag.close()


if __name__ == "__main__":
    unittest.main()

