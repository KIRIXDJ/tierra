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
    """Copia el demo con la malla indicada y devuelve su URI ``file://``."""
    html = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    html = reemplazar_malla(html, malla or malla_pequena())
    ruta = Path(tempfile.gettempdir()) / Path(destino).name
    ruta.write_text(html, encoding="utf-8")
    return ruta.as_uri()
