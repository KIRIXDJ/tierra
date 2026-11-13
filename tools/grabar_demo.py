"""Graba el video de respaldo de la demo (playwright + ffmpeg).

Recorre el producto actual: el monitor de la finca, riesgos, satélite NASA,
rotaciones, techo, fotos y la vuelta al globo. Deja un .webm en /tmp/video_tierra.
Para el mp4:

    python3 tools/grabar_demo.py
    ffmpeg -y -i /tmp/video_tierra/*.webm -c:v libx264 -preset slow -crf 30 \
        -pix_fmt yuv420p -movflags +faststart -an docs/demo.mp4

Uso: cuando haya que regenerar el video tras cambiar la app.
"""

import functools
import http.server
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = pathlib.Path("/tmp/video_tierra")
SALIDA.mkdir(parents=True, exist_ok=True)
for archivo in SALIDA.glob("*"):
    archivo.unlink()

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ))
socketserver.TCPServer.allow_reuse_address = True
servidor = socketserver.TCPServer(("127.0.0.1", 0), Handler)
puerto = servidor.server_address[1]
threading.Thread(target=servidor.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch(headless=True, args=["--use-angle=swiftshader",
                                                  "--enable-unsafe-swiftshader"])
    contexto = nav.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=str(SALIDA),
        record_video_size={"width": 1280, "height": 720},
    )
    pag = contexto.new_page()
    pag.goto(f"http://127.0.0.1:{puerto}/web/index.html")
    pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=60000)
    pag.wait_for_selector("#vision.visible", timeout=20000)
    pag.wait_for_timeout(3500)                                   # monitor y mapa

    # Sensores y clima arriba; luego riesgos y satélite NASA.
    pag.eval_on_selector("#vision-lado", "e => { e.scrollTop = 0; }")
    pag.wait_for_timeout(2500)
    pag.eval_on_selector("#vision-riesgos", "e => e.scrollIntoView({block: 'center'})")
    pag.wait_for_timeout(3000)
    pag.eval_on_selector("#vision-satelite", "e => e.scrollIntoView({block: 'center'})")
    pag.wait_for_timeout(3000)

    # Rotaciones: comparar y cambiar el escenario.
    pag.eval_on_selector("#rotacion-filas", "e => e.scrollIntoView({block: 'center'})")
    pag.wait_for_timeout(1500)
    pag.click("button.rotacion-fila[data-id='alternativa_1']")
    pag.wait_for_timeout(2500)
    pag.fill("#escenario-lluvia", "-40")
    pag.dispatch_event("#escenario-lluvia", "input")
    pag.wait_for_timeout(2500)

    # Techo: cerrar y abrir.
    pag.eval_on_selector("#vision-actuadores", "e => e.scrollIntoView({block: 'center'})")
    pag.wait_for_timeout(800)
    pag.click(".actuador[data-fila='techo'] button[data-val='on']")
    pag.wait_for_timeout(2500)
    pag.click(".actuador[data-fila='techo'] button[data-val='off']")
    pag.wait_for_timeout(1500)

    # Fotos de la finca: cámara simulada ampliada y cierre.
    pag.eval_on_selector("#vision-fotos", "e => e.scrollIntoView({block: 'center'})")
    pag.wait_for_timeout(800)
    pag.click(".foto-mini[data-foto='cultivo']")
    pag.wait_for_timeout(3000)
    pag.click("#vision-lightbox")
    pag.wait_for_timeout(1200)

    # Vuelta al globo y del globo a la finca (el vuelo de la demo).
    pag.click("#vision-cerrar")
    pag.wait_for_timeout(2500)
    pag.click("#chips button[data-lat='18'][data-lon='-72']")
    pag.wait_for_timeout(2500)
    pag.evaluate("window.__tierra.seleccionar(18.9, -70.7)")
    pag.wait_for_timeout(4000)
    pag.click("#panel-monitor")
    pag.wait_for_timeout(4500)
    pag.wait_for_timeout(1500)
    contexto.close()
    nav.close()

servidor.shutdown()
print("grabado:", [archivo.name for archivo in SALIDA.glob("*")])
