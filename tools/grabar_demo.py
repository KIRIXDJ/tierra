"""Graba el video de respaldo de la demo (playwright + ffmpeg).

Recorre el guion completo y deja un .webm en /tmp/video_tierra. Para el mp4:

    python3 tools/grabar_demo.py
    ffmpeg -y -i /tmp/video_tierra/*.webm -c:v libx264 -preset slow -crf 30 \
        -pix_fmt yuv420p -movflags +faststart -an docs/demo.mp4

Uso: cuando haya que regenerar el video tras cambiar la app.
"""

import http.server, socketserver, threading, functools, pathlib, shutil
from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = pathlib.Path("/tmp/video_tierra")
for f in SALIDA.glob("*"):
    f.unlink()

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ))
socketserver.TCPServer.allow_reuse_address = True
s = socketserver.TCPServer(("127.0.0.1", 0), Handler); puerto = s.server_address[1]
threading.Thread(target=s.serve_forever, daemon=True).start()

with sync_playwright() as p:
    nav = p.chromium.launch(headless=True, args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    ctx = nav.new_context(viewport={"width":1280,"height":720},
                          record_video_dir=str(SALIDA), record_video_size={"width":1280,"height":720})
    pag = ctx.new_page()
    pag.goto(f"http://127.0.0.1:{puerto}/web/index.html")
    pag.wait_for_function("window.__tierra.listo", timeout=60000)
    pag.wait_for_timeout(3000)                       # portada y globo girando
    pag.click("#chips button[data-lat='18'][data-lon='-72']")
    pag.wait_for_timeout(2000)
    pag.evaluate("window.__tierra.seleccionar(18.9, -70.7)")
    pag.wait_for_timeout(4000)                       # panel de celda
    pag.click("#finca-boton"); pag.wait_for_timeout(5000)   # temporada
    pag.select_option("#finca-selector", "azua"); pag.wait_for_timeout(4000)
    pag.click("#rotaciones-boton"); pag.wait_for_timeout(4000)
    pag.fill("#peso-agua","9"); pag.dispatch_event("#peso-agua","input"); pag.wait_for_timeout(2500)
    pag.fill("#escenario-lluvia","-40"); pag.dispatch_event("#escenario-lluvia","input"); pag.wait_for_timeout(3000)
    pag.click("#vision-boton"); pag.wait_for_timeout(2500)
    pag.fill("#vision-humedad","6"); pag.dispatch_event("#vision-humedad","input"); pag.wait_for_timeout(2000)
    pag.fill("#vision-lluvia","5"); pag.dispatch_event("#vision-lluvia","input"); pag.wait_for_timeout(2500)
    pag.click("#vision-telegram"); pag.wait_for_timeout(2500)
    pag.click("#metodo-boton"); pag.wait_for_timeout(4000)
    pag.click("#elio-boton"); pag.wait_for_timeout(1000)
    pag.fill("#elio-pregunta","¿está seco en Azua?"); pag.click("#elio-enviar"); pag.wait_for_timeout(4000)
    pag.keyboard.press("Escape"); pag.wait_for_timeout(2500)
    ctx.close()
    nav.close()
s.shutdown()
print("grabado:", [f.name for f in SALIDA.glob("*")])
