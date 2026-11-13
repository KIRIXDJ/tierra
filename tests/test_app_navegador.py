"""Prueba de humo de la app real en un navegador.

Abre ``web/index.html`` servido por http, espera a que el globo esté listo y
recorre las pestañas. Es el test que evita que la demo se rompa sin avisar.
Necesita playwright y un navegador: si no están, se salta.
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

    def abrir(self, estado_bot=None):
        pag = self.nav.new_page(viewport={"width": 1366, "height": 768})
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
        pag.route("**/datos/estado_finca.json*", lambda ruta: ruta.abort())
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

        # Mi parcela y el bot funcionan sin red (datos y mapa son locales).
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        self.assertIn("HUMEDAD", pag.inner_text("#parcela-lecturas"))
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))

        pag.click("#elio-boton")
        pag.wait_for_selector("#elio.visible")
        pag.fill("#elio-pregunta", "¿cómo va la temporada?")
        pag.click("#elio-enviar")
        respuesta = pag.inner_text("#elio-respuesta")
        self.assertTrue(respuesta.strip())
        self.assertNotIn("No tengo ese dato", respuesta)

        self.assertEqual(errores, [], "errores de JS con la red caída")
        pag.close()

    def test_parcela_seleccionable(self):
        """La demo es de UNA parcela: se elige, muestra sus datos y reacciona."""
        pag, errores = self.abrir()
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")

        aviso = pag.inner_text("#vision-aviso-campo")
        self.assertIn("Vista de demostración", aviso)
        self.assertIn("simulados", aviso)
        self.assertIn("@climaxeliobot", aviso)

        # Hay parcelas registradas y se puede elegir.
        opciones = pag.eval_on_selector_all("#parcela-selector option", "e => e.map(x => x.textContent)")
        self.assertGreaterEqual(len(opciones), 2)
        self.assertIn("ha", opciones[0])

        # Las lecturas muestran humedad, temperatura, riego, ventilación, techo, lluvia.
        ficha = pag.inner_text("#parcela-lecturas")
        for campo in ("HUMEDAD", "TEMPERATURA", "RIEGO", "VENTILA", "TECHO", "LLUVIA", "PLANTAS"):
            self.assertIn(campo, ficha)
        self.assertIn("Cámara", pag.inner_text("#parcela-camara"))

        # Cambiar de parcela cambia los datos (temperatura distinta y área).
        primera = pag.inner_text("#parcela-lecturas")
        pag.select_option("#parcela-selector", "el-hoyo")
        pag.wait_for_timeout(500)
        self.assertNotEqual(primera, pag.inner_text("#parcela-lecturas"))

        # Con humedad baja riega; con lluvia cierra el techo.
        pag.fill("#vision-humedad", "6")
        pag.dispatch_event("#vision-humedad", "input")
        self.assertIn("RIEGO", pag.inner_text("#parcela-lecturas"))
        pag.fill("#vision-lluvia", "5")
        pag.dispatch_event("#vision-lluvia", "input")
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))

        # Ventilación (invernadero) y plantas georreferenciadas.
        self.assertIn("VENTILA", pag.inner_text("#parcela-lecturas"))
        self.assertIn("PLANTAS", pag.inner_text("#parcela-lecturas"))
        plantas = pag.evaluate(
            "window.__tierra.plantasDeParcela(window.__tierra.parcelaActual()).length")
        self.assertGreater(plantas, 50)

        # Control por Telegram (el bot responde y cambia los actuadores).
        pag.fill("#chat-texto", "/riego off")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Riego cerrado", pag.inner_text("#chat-mensajes"))
        pag.fill("#chat-texto", "/techo on")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))
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
        pag.route("**/datos/estado_finca.json*", lambda ruta: ruta.abort())
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

    def test_recorrido_del_pitch(self):
        """El guion de la presentación, clic a clic. Si esto pasa, la demo no falla
        en vivo: globo, finca, cambio de finca, rotaciones, granja y método."""
        pag, errores = self.abrir()

        # 1. Globo: volar al Caribe y abrir la celda de República Dominicana.
        pag.click("#chips button[data-lat='18'][data-lon='-72']")
        pag.wait_for_timeout(300)
        pag.evaluate("window.__tierra.seleccionar(18.9, -70.7)")
        pag.wait_for_selector("#panel.visible")
        self.assertTrue(pag.inner_text("#panel-coords").strip())
        # Del globo a la finca: la celda del Caribe debe ofrecer las piloto.
        self.assertGreaterEqual(pag.eval_on_selector_all("#panel-finca button", "e => e.length"), 1)

        # 2. Finca: Constanza, con fuente y fecha.
        pag.keyboard.press("Escape")
        pag.click("#finca-boton")
        pag.wait_for_selector("#finca.visible")
        self.assertIn("Lluvia 30 d", pag.inner_text("#finca-filas"))
        self.assertIn("no NASA", pag.inner_text("#finca-pie"))

        # 3. Cambiar de finca: Azua debe actualizar los números.
        primera = pag.inner_text("#finca-filas")
        pag.select_option("#finca-selector", "azua")
        pag.wait_for_timeout(400)
        self.assertNotEqual(primera, pag.inner_text("#finca-filas"))

        # 4. Rotaciones: tabla + escenario.
        pag.click("#rotaciones-boton")
        pag.wait_for_selector("#rotaciones.visible")
        self.assertEqual(pag.eval_on_selector_all("#rotaciones-tabla tbody tr", "e => e.length"), 3)
        pag.fill("#escenario-lluvia", "-40")
        pag.dispatch_event("#escenario-lluvia", "input")
        self.assertIn("%", pag.inner_text("#escenario-valor"))

        # 5. Granja conectada: riego, techo y aviso.
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        pag.select_option("#parcela-selector", "la-loma")
        pag.wait_for_timeout(300)
        pag.fill("#vision-humedad", "5")
        pag.dispatch_event("#vision-humedad", "input")
        pag.fill("#vision-lluvia", "6")
        pag.dispatch_event("#vision-lluvia", "input")
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        pag.fill("#chat-texto", "/estado")
        pag.press("#chat-texto", "Enter")
        pag.wait_for_timeout(300)
        self.assertIn("Humedad", pag.inner_text("#chat-mensajes"))

        # 6. Volver al globo (el monitoreo tapa las pestañas) y ver Método y Elio.
        pag.click("#vision-cerrar")
        pag.wait_for_timeout(400)
        self.assertFalse(pag.is_visible("#vision"))
        pag.click("#metodo-boton")
        pag.wait_for_selector("#metodo.visible")
        self.assertIn("reanálisis", pag.inner_text("#metodo"))
        pag.click("#elio-boton")
        pag.wait_for_selector("#elio.visible")
        pag.fill("#elio-pregunta", "¿qué rotación me conviene?")
        pag.click("#elio-enviar")
        self.assertTrue(pag.inner_text("#elio-respuesta").strip())

        self.assertEqual(errores, [], "el guion dejó errores de JS")
        pag.close()


    def test_monitor_mapa_grande_y_fotos(self):
        """El mapa manda en la vista (no una esquina) y las dos fotos se dibujan."""
        pag, errores = self.abrir()
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
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
        # La foto de cultivo es la simulada y lo dice al ampliarla.
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
        """Abrir/cerrar el techo como el invernadero de Hiroki, y se ve en pantalla."""
        pag, errores = self.abrir()
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        pag.select_option("#parcela-selector", "el-hoyo")
        pag.wait_for_timeout(200)
        pag.click("button[data-act='techo'][data-val='on']")
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        self.assertTrue(pag.evaluate("window.__tierra.parcelaActual().id") == "el-hoyo")
        pag.click("button[data-act='techo'][data-val='off']")
        self.assertIn("abierto", pag.inner_text("#parcela-lecturas"))
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
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        pag.wait_for_function(
            "document.getElementById('vision-bot').textContent.includes('conectado')",
            timeout=15000)
        self.assertIn("cerr.", pag.inner_text("#parcela-lecturas"))
        self.assertIn("Telegram", pag.inner_text("#chat-mensajes"))
        self.assertIn("conectado", pag.inner_text("#vision-bot"))
        self.assertEqual(errores, [])
        pag.close()

    def test_monitor_en_el_movil(self):
        """El monitoreo también entra en un teléfono: mapa arriba, panel debajo."""
        pag = self.nav.new_page(viewport={"width": 390, "height": 844},
                                is_mobile=True, has_touch=True)
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.route("**/datos/estado_finca.json*", lambda ruta: ruta.abort())
        pag.goto(f"{self.base}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
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
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        pag.set_input_files("#vision-archivo", str(ruta))
        pag.wait_for_function("document.getElementById('vision-diagnostico').textContent.includes('amarillo')",
                              timeout=15000)
        texto = pag.inner_text("#vision-diagnostico")
        self.assertIn("clorosis", texto)
        self.assertIn("amarillo", texto)
        self.assertIn("Mide color", texto)
        pag.close()

    def test_registrar_parcela_dibujando(self):
        """El agricultor dibuja su parcela sobre el mapa y se calcula el área."""
        pag, errores = self.abrir()
        pag.click("#vision-boton")
        pag.wait_for_selector("#vision.visible")
        antes = pag.eval_on_selector_all("#parcela-selector option", "e => e.length")

        pag.click("#vision-registrar")
        caja = pag.locator("#vision-mapa").bounding_box()
        for fx, fy in [(0.35, 0.30), (0.62, 0.28), (0.66, 0.62), (0.33, 0.64)]:
            pag.mouse.click(caja["x"] + caja["width"] * fx, caja["y"] + caja["height"] * fy)
            pag.wait_for_timeout(120)
        self.assertIn("esquinas", pag.inner_text("#vision-dibujo-info"))

        pag.click("#vision-terminar")
        pag.wait_for_timeout(500)
        despues = pag.eval_on_selector_all("#parcela-selector option", "e => e.length")
        self.assertEqual(despues, antes + 1)
        self.assertIn("Mi parcela", pag.inner_text("#parcela-selector"))
        # El área calculada tiene que ser un número positivo y razonable.
        area = pag.evaluate("window.__tierra.parcelaActual().area_ha")
        self.assertGreater(area, 0.05)
        self.assertLess(area, 50)
        self.assertEqual(errores, [])
        pag.close()


if __name__ == "__main__":
    unittest.main()

