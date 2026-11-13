"""Prueba del deck de la presentación (sin red, con playwright).

Comprueba que las 12 diapositivas entran en 16:9 y en 4:3, que las imágenes
cargan y que la navegación y el contador funcionan. Si no hay playwright, se
salta: el deck es estático y no debe romper el CI.
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


class TestDeck(unittest.TestCase):
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

    def abrir(self, ancho, alto):
        pag = self.nav.new_page(viewport={"width": ancho, "height": alto})
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"{self.base}/docs/deck/index.html")
        pag.wait_for_timeout(400)
        return pag, errores

    def test_diapositivas_entran_en_16_9_y_4_3(self):
        for ancho, alto in ((1280, 720), (1024, 768), (1920, 1080)):
            pag, errores = self.abrir(ancho, alto)
            self.assertEqual(errores, [])
            total = pag.eval_on_selector_all(".slide", "e => e.length")
            self.assertEqual(total, 12)
            self.assertIn(f"1 / {total}", pag.inner_text("#contador"))
            for numero in range(total):
                activa = pag.eval_on_selector(
                    ".slide.active",
                    """e => ({
                        cabecera: (e.querySelector('h2, h1') || {}).textContent || 'sin título',
                        alto: e.scrollHeight,
                        visible: e.clientHeight,
                    })""")
                self.assertLessEqual(
                    activa["alto"], activa["visible"] + 2,
                    f"{ancho}x{alto}: la diapositiva {numero + 1} "
                    f"({activa['cabecera']}) se sale verticalmente")
                pag.keyboard.press("ArrowRight")
                pag.wait_for_timeout(120)
                esperado = min(numero + 2, total)
                self.assertEqual(pag.inner_text("#contador"), f"{esperado} / {total}")
            pag.close()

    def test_imagenes_y_navegacion(self):
        pag, errores = self.abrir(1280, 720)
        imagenes = pag.eval_on_selector_all(
            "img", "e => e.map(x => [x.naturalWidth, x.getAttribute('src')])")
        self.assertGreaterEqual(len(imagenes), 3)
        for ancho, origen in imagenes:
            self.assertGreater(ancho, 0, f"imagen sin cargar: {origen}")
        pag.keyboard.press("End")
        pag.wait_for_timeout(200)
        self.assertEqual(pag.inner_text("#contador"), "12 / 12")
        pag.keyboard.press("Home")
        pag.wait_for_timeout(200)
        self.assertEqual(pag.inner_text("#contador"), "1 / 12")
        self.assertEqual(errores, [])
        pag.close()


if __name__ == "__main__":
    unittest.main()
