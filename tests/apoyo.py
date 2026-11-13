"""Utilidades de las pruebas de navegador: HTML con una malla pequeña."""

import tempfile
from pathlib import Path

from tools.html_malla import reemplazar_malla

RAIZ = Path(__file__).resolve().parent.parent


def malla_pequena():
    """Cuatro celdas de 5° con valores conocidos para las pruebas."""
    variables = [
        {"id": "T2M", "nombre": "Temperatura", "unidad": "°C/década", "dominio": 0.8},
        {"id": "PRECTOTCORR", "nombre": "Lluvia",
         "unidad": "mm/año por década", "dominio": 80.0},
        {"id": "WS2M", "nombre": "Viento", "unidad": "m/s por década", "dominio": 0.15},
        {"id": "RH2M", "nombre": "Humedad", "unidad": "%/década", "dominio": 2.0},
    ]
    celdas = [
        [17.5, -72.5, 0.26, 0.0001, 25.0,
         -12.3, 0.42, 1100.0, -0.01, 0.6, 4.1, 0.3, 0.01, 78.0, 12, 3],
        [-2.5, -62.5, 0.33, 0.0001, 26.0,
         40.0, 0.2, 1600.0, 0.0, 0.9, 3.0, 0.2, 0.3, 85.0, 2, 0],
        [47.5, 12.5, 0.53, 0.00001, 9.0,
         10.0, 0.5, 900.0, 0.02, 0.2, 5.0, -0.1, 0.4, 75.0, 0, 1],
        [77.5, 17.5, 0.72, 0.000001, -5.0,
         None, None, None, 0.01, 0.3, 6.0, -0.2, 0.05, 80.0, 0, 0],
    ]
    return {
        "version": 1,
        "res": 5,
        "anio_ini": 1984,
        "anio_fin": 2025,
        "variables": variables,
        "celdas": celdas,
    }


def html_de_prueba(destino, malla=None):
    """Copia el demo con la malla indicada y devuelve su URI ``file://``.

    Replica la estructura del repo (``web/vendor``, ``web/elio.js``, ``datos``,
    ``textures``) porque el demo carga esas rutas relativas y sin ellas el
    módulo no arrancaría: así la prueba ve la app real, no un HTML suelto.
    """
    import shutil

    base = Path(tempfile.gettempdir()) / f"tierra_prueba_{Path(destino).stem}"
    if base.exists():
        shutil.rmtree(base)
    (base / "web").mkdir(parents=True)

    html = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    html = reemplazar_malla(html, malla or malla_pequena())
    (base / "web" / "index.html").write_text(html, encoding="utf-8")

    shutil.copy2(RAIZ / "web" / "elio.js", base / "web" / "elio.js")
    shutil.copytree(RAIZ / "web" / "vendor", base / "web" / "vendor")
    for carpeta in ("datos", "textures"):
        origen = RAIZ / carpeta
        if origen.is_dir():
            shutil.copytree(origen, base / carpeta)
    return (base / "web" / "index.html").as_uri()


# Chromium bloquea módulos desde file:// salvo con este flag: el test abre el HTML
# copiado con file://, así que lo necesita.
ARGUMENTOS_FILE = ["--allow-file-access-from-files"]
