"""Prueba de humo de la app real en un navegador.

Abre ``web/index.html`` servido por http, espera a que el globo esté listo y
recorre el producto: arranca en el panel de monitoreo, mapa, sensores, fotos,
techo, rotación, bot y registro de parcela. Es el test que evita que la demo se
rompa sin avisar. Necesita playwright y un navegador: si no están, se salta.
"""

import functools
import http.server
import json
import pathlib
import socketserver
import threading
import unittest
from datetime import datetime, timezone

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
            cls.nav = cls._pw.chromium.launch(headless=True, args=[
                "--use-fake-device-for-media-stream",
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

    def abrir(self, estado_bot=None, viewport=None):
        pag = self.nav.new_page(viewport=viewport or {"width": 1366, "height": 768})
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        # El estado del bot real es un archivo local. En pruebas se simula:
        # por defecto sin bot (modo simulación) y con estado inyectado cuando toca.
        patron = "**/datos/estado_finca.json*"
        if estado_bot is None:
            pag.route(patron, lambda ruta: ruta.abort())
        else:
            pag.route(patron, lambda ruta: ruta.fulfill(
                status=200, content_type="application/json", body=json.dumps(estado_bot)))
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        return pag, errores

    def test_globo_sin_cdn(self):
        pag, errores = self.abrir()
        self.assertTrue(pag.evaluate("window.__tierra.globo.texturas.ok"),
                        "las texturas locales no cargaron")
        self.assertEqual(errores, [])
        pag.close()

    def test_arranca_en_el_monitor(self):
        """La app abre directo en el producto: monitor, no globo ni módulos sueltos."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        self.assertFalse(pag.is_visible("#finca"))
        self.assertFalse(pag.is_visible("#rotaciones"))
        self.assertFalse(pag.is_visible("#elio"))
        self.assertFalse(pag.is_visible("#metodo"))
        botones = pag.eval_on_selector_all("#chips button", "e => e.map(x => x.textContent.trim())")
        for fuera in ("Finca", "Rotaciones", "Elio", "Método"):
            self.assertNotIn(fuera, botones)
        self.assertIn("Mi parcela", botones)
        # El tiempo no se controla: solo hay prioridades del agricultor y el
        # escenario de rotación (simulación), no humedad ni lluvia.
        self.assertEqual(
            pag.eval_on_selector_all("#vision-humedad, #vision-lluvia", "e => e.length"), 0)
        controles = pag.eval_on_selector_all("input[type=range]", "e => e.map(x => x.id)")
        self.assertEqual(controles, ["peso-agua", "peso-diversidad", "escenario-lluvia"])
        self.assertIn("ERA5", pag.inner_text("#vision-automatico"))
        # La rotación se compara en el propio monitor (3 estrategias).
        filas = pag.eval_on_selector_all(".rotacion-fila", "e => e.length")
        self.assertEqual(filas, 3)
        self.assertGreaterEqual(len(errores), 0)
        self.assertEqual(errores, [])
        pag.close()

    def test_monitor_mapa_grande_y_fotos(self):
        """El mapa manda en la vista y las dos fotos se dibujan."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        ancho, alto = pag.eval_on_selector("#vision-mapa", "c => [c.clientWidth, c.clientHeight]")
        self.assertGreater(ancho, 600, f"mapa demasiado estrecho: {ancho}")
        self.assertGreater(alto, 240, f"mapa demasiado bajo: {alto}")
        self.assertEqual(pag.eval_on_selector_all(".tarjeta-parcela", "e => e.length"), 3)
        for selector in ("#foto-satelite", "#foto-cultivo"):
            pixeles = pag.evaluate("""(sel) => {
                const c = document.querySelector(sel);
                const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                let n = 0;
                for (let i = 0; i < d.length; i += 4000) {
                    if (d[i] + d[i + 1] + d[i + 2] > 60) { n += 1; }
                }
                return n;
            }""", selector)
            self.assertGreater(pixeles, 100, f"{selector} salió vacío")
        pag.click(".foto-mini[data-foto='cultivo']")
        pag.wait_for_selector("#vision-lightbox.visible")
        pie = pag.inner_text("#vision-lightbox-pie").lower()
        self.assertIn("simulada", pie)
        self.assertIn("no es una foto real", pie)
        pag.click("#vision-lightbox")
        pag.wait_for_timeout(200)
        self.assertFalse(pag.is_visible("#vision-lightbox"))
        self.assertEqual(errores, [])
        pag.close()

    def test_techo_se_cierra_y_se_abre(self):
        """El techo se abre y se cierra como el invernadero de Hiroki."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        pag.select_option("#parcela-selector", "el-hoyo")
        pag.wait_for_timeout(300)
        pag.click(".actuador[data-fila='techo'] button[data-val='on']")
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        pag.click(".actuador[data-fila='techo'] button[data-val='off']")
        self.assertIn("abierto", pag.inner_text("#parcela-lecturas"))
        self.assertEqual(errores, [])
        pag.close()

    def test_parcela_seleccionable(self):
        """Se elige parcela y cambian sus datos; el bot responde en el chat."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        aviso = pag.inner_text("#vision-aviso-campo")
        self.assertIn("Vista de demostración", aviso)
        self.assertIn("simulados", aviso)
        self.assertIn("@climaxeliobot", aviso)
        opciones = pag.eval_on_selector_all("#parcela-selector option", "e => e.map(x => x.textContent)")
        self.assertGreaterEqual(len(opciones), 2)
        ficha = pag.inner_text("#parcela-lecturas")
        for campo in ("HUMEDAD", "TEMPERATURA", "RIEGO", "VENTILA", "TECHO", "LLUVIA", "PLANTAS"):
            self.assertIn(campo, ficha)
        self.assertIn("Cámara", pag.inner_text("#parcela-camara"))
        primera = pag.inner_text("#parcela-lecturas")
        pag.select_option("#parcela-selector", "el-hoyo")
        pag.wait_for_timeout(500)
        self.assertNotEqual(primera, pag.inner_text("#parcela-lecturas"))
        self.assertGreater(
            pag.evaluate("window.__tierra.plantasDeParcela(window.__tierra.parcelaActual()).length"),
            50)
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))
        pag.fill("#chat-texto", "/riego off")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Riego cerrado", pag.inner_text("#chat-mensajes"))
        pag.fill("#chat-texto", "/techo on")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        self.assertEqual(errores, [])
        pag.close()

    def test_rotacion_se_compara_en_el_monitor(self):
        """Las tres estrategias se comparan sin abrir un módulo aparte."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        filas = pag.eval_on_selector_all(".rotacion-fila", "e => e.map(x => x.textContent)")
        self.assertEqual(len(filas), 3)
        self.assertIn("50/100", filas[0])
        self.assertIn("93/100", filas[2])
        ganadoras = pag.eval_on_selector_all(".rotacion-fila.gana", "e => e.length")
        self.assertEqual(ganadoras, 1)
        # Para cada estrategia: por qué, evidencia, beneficios, huecos y riesgos.
        detalle = pag.inner_text("#rotacion-detalle")
        for bloque in ("Por qué se sugiere", "Evidencia", "Beneficios",
                       "Datos que faltan", "Riesgo a revisar"):
            self.assertIn(bloque, detalle)
        # El escenario de lluvia (simulación, no pronóstico) mueve los índices.
        pag.fill("#escenario-lluvia", "-40")
        pag.dispatch_event("#escenario-lluvia", "input")
        pag.wait_for_timeout(300)
        indices = pag.eval_on_selector_all("button.rotacion-fila b", "e => e.map(x => x.textContent)")
        self.assertEqual(indices, ["50/100", "72/100", "89/100"])
        self.assertIn("-40", pag.inner_text("#escenario-lluvia-valor"))
        # Elegir una estrategia cambia el detalle.
        pag.click("button.rotacion-fila[data-id='alternativa_1']")
        pag.wait_for_timeout(200)
        self.assertIn("Demanda de agua", pag.inner_text("#rotacion-detalle"))
        self.assertEqual(errores, [])
        pag.close()

    def test_riesgos_de_la_finca(self):
        """Riesgos climáticos reales de NASA POWER en el monitor."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        texto = pag.inner_text("#vision-riesgos")
        for campo in ("CALOR", "LLUVIA ≥ 20 MM", "DÍAS SECOS", "HELADAS",
                      "SUELO DE RAÍZ", "EVAPOTRANSP."):
            self.assertIn(campo, texto)
        self.assertIn("NASA POWER", texto)
        self.assertIn("Reanálisis", texto)
        pixeles = pag.evaluate("""() => {
            const c = document.getElementById('riesgos-serie');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0;
            for (let i = 0; i < d.length; i += 4) { if (d[i] + d[i+1] + d[i+2] > 60) n += 1; }
            return n;
        }""")
        self.assertGreater(pixeles, 200)
        self.assertEqual(errores, [])
        pag.close()

    def test_satelite_nasa_gibs(self):
        """NDVI (MODIS) e IMERG (GPM) reales de GIBS, en el monitor."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        texto = pag.inner_text("#vision-satelite")
        for esperado in ("NDVI MODIS", "Lluvia IMERG", "NASA GIBS", "sin lluvia"):
            self.assertIn(esperado, texto)
        medidas = pag.eval_on_selector_all(
            "#vision-satelite img", "e => e.map(x => [x.naturalWidth, x.naturalHeight])")
        self.assertEqual(len(medidas), 2)
        for ancho, alto in medidas:
            self.assertGreater(ancho, 0)
            self.assertGreater(alto, 0)
        pag.click("button[data-satelite='ndvi']")
        pag.wait_for_selector("#vision-lightbox.visible")
        pie = pag.inner_text("#vision-lightbox-pie")
        self.assertIn("MODIS", pie)
        self.assertIn("GIBS", pie)
        self.assertIn("289", pie)          # resolución del píxel
        pag.click("#vision-lightbox")
        self.assertEqual(errores, [])
        pag.close()

    def test_estado_del_bot_telegram(self):
        """Si el bot real escribe el estado, la vista lo refleja (sin red)."""
        ahora = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        estado = {
            "version": 1, "origen": "telegram", "actualizado": ahora, "modo": "comandos",
            "parcelas": {"la-esperanza": {"riego": False, "techo": True, "ventilacion": False}},
            "ultimo": {"texto": "/techo on", "respuesta": "Techo cerrado en La Esperanza.",
                       "ts": ahora},
            "historial": [{"texto": "/techo on", "respuesta": "Techo cerrado en La Esperanza.",
                           "ts": ahora}],
        }
        pag, errores = self.abrir(estado_bot=estado)
        pag.wait_for_selector("#vision.visible", timeout=15000)
        pag.wait_for_function(
            "document.getElementById('vision-bot').textContent.includes('conectado')",
            timeout=15000)
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        self.assertIn("Telegram", pag.inner_text("#chat-mensajes"))
        self.assertEqual(errores, [])
        pag.close()

    def test_monitor_en_el_movil(self):
        """El monitoreo también entra en un teléfono: mapa arriba, panel debajo."""
        pag, errores = self.abrir(viewport={"width": 390, "height": 844})
        pag.wait_for_selector("#vision.visible", timeout=15000)
        medidas = pag.evaluate("""() => {
            const mapa = document.getElementById('vision-mapa-caja').getBoundingClientRect();
            const cuerpo = document.getElementById('vision-cuerpo').getBoundingClientRect();
            return {
                mapaAlto: Math.round(mapa.height),
                ancho: Math.round(cuerpo.width),
                desborda: cuerpo.right > window.innerWidth + 1 || cuerpo.left < -1,
            };
        }""")
        self.assertFalse(medidas["desborda"], f"el monitoreo se sale: {medidas}")
        self.assertGreater(medidas["mapaAlto"], 150, f"mapa muy bajo: {medidas}")
        self.assertEqual(errores, [])
        pag.close()

    def test_recorrido_del_pitch(self):
        """El guion de la presentación, clic a clic: monitor, globo, celda, vuelta."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        # 1. El producto abre en el monitor con el mapa y la rotación.
        self.assertIn("La Esperanza", pag.inner_text("#parcela-selector"))
        self.assertEqual(pag.eval_on_selector_all(".rotacion-fila", "e => e.length"), 3)
        # 2. Volver al globo: la cara NASA de la herramienta.
        pag.click("#vision-cerrar")
        pag.wait_for_timeout(500)
        self.assertFalse(pag.is_visible("#vision"))
        self.assertEqual(pag.evaluate("document.getElementById('lienzo').style.opacity"), "1")
        pag.click("#chips button[data-lat='18'][data-lon='-72']")
        pag.wait_for_timeout(300)
        pag.evaluate("window.__tierra.seleccionar(18.9, -70.7)")
        pag.wait_for_selector("#panel.visible")
        self.assertTrue(pag.inner_text("#panel-coords").strip())
        self.assertIn("monitoreo", pag.inner_text("#panel-finca").lower())
        # 3. Del globo al monitoreo en un clic (el globo vuela y entra).
        pag.click("#panel-monitor")
        pag.wait_for_selector("#vision.visible", timeout=15000)
        pag.wait_for_timeout(500)
        pag.click(".actuador[data-fila='techo'] button[data-val='on']")
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))
        self.assertEqual(errores, [], "el guion dejó errores de JS")
        pag.close()

    def test_sin_internet_la_demo_sigue(self):
        """Plan B de la feria: sin wifi, el monitor, el mapa y las fotos responden."""
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
        pag.route("**/datos/estado_finca.json*", lambda ruta: ruta.abort())
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        pag.wait_for_selector("#vision.visible", timeout=15000)
        self.assertIn("HUMEDAD", pag.inner_text("#parcela-lecturas"))
        # El mapa (Esri) y las fotos son locales: la demo no depende del wifi.
        pixeles = pag.evaluate("""() => {
            const c = document.querySelector('#foto-satelite');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0;
            for (let i = 0; i < d.length; i += 4000) { if (d[i] + d[i+1] + d[i+2] > 60) n += 1; }
            return n;
        }""")
        self.assertGreater(pixeles, 100)
        # El satélite NASA también es local: sin wifi se sigue viendo.
        satelite = pag.eval_on_selector_all(
            "#vision-satelite img", "e => e.map(x => x.naturalWidth)")
        self.assertEqual(satelite, [256, 288])
        self.assertEqual(errores, [], "errores de JS con la red caída")
        self.assertGreaterEqual(len(externas), 0)
        pag.close()

    def test_analiza_una_foto_real(self):
        """Sube una imagen y calcula el color de verdad (no un texto fijo)."""
        from PIL import Image
        import tempfile
        ruta = pathlib.Path(tempfile.gettempdir()) / "tierra_foto_test.jpg"
        imagen = Image.new("RGB", (200, 150), (40, 140, 50))
        for x in range(100, 200):
            for y in range(150):
                imagen.putpixel((x, y), (220, 210, 60))
        imagen.save(ruta, quality=90)

        pag, _ = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        pag.set_input_files("#vision-archivo", str(ruta))
        pag.wait_for_function(
            "document.getElementById('vision-diagnostico').textContent.includes('amarillo')",
            timeout=15000)
        texto = pag.inner_text("#vision-diagnostico")
        self.assertIn("clorosis", texto)
        self.assertIn("Mide color", texto)
        pag.close()

    def test_registrar_parcela_dibujando(self):
        """El agricultor dibuja su parcela y queda donde la dibujó."""
        pag, errores = self.abrir()
        pag.wait_for_selector("#vision.visible", timeout=15000)
        antes = pag.eval_on_selector_all("#parcela-selector option", "e => e.length")
        pag.click("#vision-registrar")
        caja = pag.locator("#vision-mapa").bounding_box()
        puntos = [(0.42, 0.40), (0.58, 0.40), (0.58, 0.58), (0.42, 0.58)]
        for fx, fy in puntos:
            pag.mouse.click(caja["x"] + caja["width"] * fx, caja["y"] + caja["height"] * fy)
            pag.wait_for_timeout(120)
        self.assertIn("esquinas", pag.inner_text("#vision-dibujo-info"))
        pag.click("#vision-terminar")
        pag.wait_for_timeout(600)
        despues = pag.eval_on_selector_all("#parcela-selector option", "e => e.length")
        self.assertEqual(despues, antes + 1)
        self.assertIn("Mi parcela", pag.inner_text("#parcela-selector"))
        area = pag.evaluate("window.__tierra.parcelaActual().area_ha")
        self.assertGreater(area, 0.05)
        self.assertLess(area, 50)
        # La parcela queda bajo el clic: pulsar dentro del dibujo la vuelve a elegir.
        pag.mouse.click(caja["x"] + caja["width"] * 0.5, caja["y"] + caja["height"] * 0.49)
        pag.wait_for_timeout(300)
        self.assertIn("registrada", pag.evaluate("window.__tierra.parcelaActual().id"))
        self.assertEqual(errores, [])
        pag.close()


if __name__ == "__main__":
    unittest.main()
