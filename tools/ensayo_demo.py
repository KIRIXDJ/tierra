"""Ensayo cronometrado de la demo de 3 minutos.

Recorre las acciones de pantalla del guion (`docs/pitch-3min.md`) y mide cuánto
tardan, para saber cuánto tiempo queda para hablar en cada bloque. No mide la
voz: eso es del presentador.

Uso:
    python3 tools/ensayo_demo.py            # imprime la tabla y escribe docs/ensayo-tiempos.md
"""

from __future__ import annotations

import functools
import http.server
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "ensayo-tiempos.md"

# (bloque, segundos objetivo del pitch, acción)
BLOQUES = [
    ("1 · Gancho", 15, "mirar la finca y señalar el mapa"),
    ("2 · Problema", 30, "bajar a Riesgos y leer calor, lluvia intensa y días secos"),
    ("3 · Solución", 40, "mapa, satélite NASA y rotación con el escenario de lluvia"),
    ("4 · Propuesta de valor", 30, "abrir Método y límites y volver al panel"),
    ("5 · Modelo de negocio", 20, "mostrar el chat del bot y el estado de los actuadores"),
    ("6 · Impacto", 20, "techo: cerrar y abrir (automatización visible)"),
    ("7 · Cierre", 15, "volver al globo y regresar a la finca con el botón del monitoreo"),
]


def servir():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ))
    socketserver.TCPServer.allow_reuse_address = True
    servidor = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, servidor.server_address[1]


def cronometrar(pag, accion):
    inicio = pag.evaluate("performance.now()")
    accion()
    return (pag.evaluate("performance.now()") - inicio) / 1000


def main():
    servidor, puerto = servir()
    filas = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=["--use-angle=swiftshader",
                                                      "--enable-unsafe-swiftshader"])
        pag = nav.new_page(viewport={"width": 1366, "height": 768})
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(f"http://127.0.0.1:{puerto}/web/index.html")
        pag.wait_for_function("window.__tierra && window.__tierra.listo", timeout=90000)
        pag.wait_for_selector("#vision.visible", timeout=20000)
        pag.wait_for_timeout(1200)
        pag.route("**/datos/estado_finca.json*", lambda ruta: ruta.abort())

        for nombre, objetivo, _detalle in BLOQUES:
            if nombre.startswith("1"):
                accion = lambda: pag.wait_for_timeout(1200)
            elif nombre.startswith("2"):
                accion = lambda: (pag.eval_on_selector(
                    "#vision-riesgos", "e => e.scrollIntoView({block: 'center'})"),
                    pag.wait_for_timeout(900))
            elif nombre.startswith("3"):
                def accion():
                    pag.eval_on_selector("#vision-satelite",
                                         "e => e.scrollIntoView({block: 'center'})")
                    pag.wait_for_timeout(900)
                    pag.eval_on_selector("#rotacion-filas",
                                         "e => e.scrollIntoView({block: 'center'})")
                    pag.wait_for_timeout(600)
                    pag.click("button.rotacion-fila[data-id='alternativa_1']")
                    pag.fill("#escenario-lluvia", "-40")
                    pag.dispatch_event("#escenario-lluvia", "input")
                    pag.wait_for_timeout(800)
            elif nombre.startswith("4"):
                def accion():
                    pag.click("#vision-metodo summary")
                    pag.wait_for_timeout(600)
                    pag.eval_on_selector("#vision-lado", "e => { e.scrollTop = 0; }")
                    pag.wait_for_timeout(500)
            elif nombre.startswith("5"):
                def accion():
                    pag.eval_on_selector("#vision-chat", "e => e.scrollIntoView({block: 'center'})")
                    pag.wait_for_timeout(900)
            elif nombre.startswith("6"):
                def accion():
                    pag.eval_on_selector("#vision-actuadores",
                                         "e => e.scrollIntoView({block: 'center'})")
                    pag.wait_for_timeout(400)
                    pag.click(".actuador[data-fila='techo'] button[data-val='on']")
                    pag.wait_for_timeout(700)
                    pag.click(".actuador[data-fila='techo'] button[data-val='off']")
                    pag.wait_for_timeout(500)
            else:
                def accion():
                    pag.click("#vision-cerrar")
                    pag.wait_for_timeout(600)
                    pag.evaluate("window.__tierra.seleccionar(18.9, -70.7)")
                    pag.wait_for_timeout(600)
                    pag.click("#panel-monitor")
                    pag.wait_for_selector("#vision.visible", timeout=15000)
                    pag.wait_for_timeout(600)
            segundos = cronometrar(pag, accion)
            filas.append((nombre, objetivo, segundos, _detalle))

        nav.close()
    servidor.shutdown()

    total_acciones = sum(fila[2] for fila in filas)
    lineas = [
        "# Ensayo cronometrado de la demo",
        "",
        f"Generado por `tools/ensayo_demo.py` el "
        f"{__import__('datetime').datetime.now().astimezone().isoformat(timespec='seconds')}.",
        "",
        "Mide solo las **acciones de pantalla**; el resto del tiempo de cada bloque es voz.",
        "",
        "| Bloque | Objetivo | Acciones | Acción de pantalla |",
        "|---|---|---|---|",
    ]
    for nombre, objetivo, segundos, detalle in filas:
        lineas.append(f"| {nombre} | {objetivo} s | {segundos:.1f} s | {detalle} |")
    lineas += [
        "",
        f"**Total de acciones de pantalla: {total_acciones:.1f} s** de 180 s. "
        f"Quedan ~{180 - total_acciones:.0f} s para hablar y respirar.",
        "",
        f"Errores de JS durante el ensayo: {len(errores)}.",
        "",
        "Si un bloque se pasa, recortar del 2 (problema) y del 6 (impacto), nunca del cierre.",
    ]
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas[:20]))
    print(f"\nEscrito {SALIDA.relative_to(RAIZ)} · errores: {len(errores)}")


if __name__ == "__main__":
    main()
