import datetime as dt
import json
import os
import shutil
import unittest
import uuid
from zoneinfo import ZoneInfo

from tools import reciente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carpeta_temporal():
    """Carpeta temporal dentro del repo (``mkdtemp`` deja permisos que no se borran)."""
    carpeta = os.path.join(RAIZ, f"_tmp_reciente_{uuid.uuid4().hex[:8]}")
    os.makedirs(carpeta)
    return carpeta


ZONA = ZoneInfo("America/Santo_Domingo")
AHORA = dt.datetime(2026, 11, 8, 12, 0, tzinfo=ZONA)
FINCA = {
    "id": "constanza",
    "nombre": "Constanza",
    "pais": "República Dominicana",
    "lat": 18.91,
    "lon": -70.74,
    "zona_horaria": "America/Santo_Domingo",
}


def diario(desde, dias, lluvia=1.0, tmax=30.0, tmin=20.0):
    """Bloque ``daily`` sintético con un valor por día."""
    fechas = [desde + dt.timedelta(days=i) for i in range(dias)]
    return {
        "daily_units": {
            "time": "iso8601",
            "precipitation_sum": "mm",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
        },
        "daily": {
            "time": [fecha.isoformat() for fecha in fechas],
            "precipitation_sum": [lluvia for _ in fechas],
            "temperature_2m_max": [tmax for _ in fechas],
            "temperature_2m_min": [tmin for _ in fechas],
        },
    }


def horario(desde, dias, valor=0.30):
    """Bloque ``hourly`` sintético de 24 valores por día."""
    marcas = []
    valores = []
    for desplazamiento in range(dias):
        dia = desde + dt.timedelta(days=desplazamiento)
        for hora in range(24):
            marcas.append(dt.datetime(dia.year, dia.month, dia.day, hora).isoformat())
            valores.append(valor)
    return {
        "hourly_units": {"time": "iso8601", "soil_moisture_0_to_7cm": "m³/m³"},
        "hourly": {"time": marcas, "soil_moisture_0_to_7cm": valores},
    }


def respuesta_completa():
    """49 días de pasado y 8 de futuro: cubre la ventana y el pronóstico."""
    inicio = dt.date(2026, 9, 20)
    datos = diario(inicio, 57)
    datos.update(horario(inicio, 57))
    return datos


def climatologia_simple(anios=5, lluvia=10.0, t2m=20.0):
    """Climatología mensual constante para probar normales y bandas."""
    return {
        str(2000 + anio): {
            "lluvia_mm": [lluvia] * 12,
            "t2m": [t2m] * 12,
        }
        for anio in range(anios)
    }


class TestPercentil(unittest.TestCase):
    def test_lista_conocida(self):
        valores = [1, 2, 3, 4]
        self.assertAlmostEqual(reciente.percentil(valores, 0.5), 2.5)
        self.assertAlmostEqual(reciente.percentil(valores, 0.25), 1.75)
        self.assertAlmostEqual(reciente.percentil(valores, 0), 1.0)
        self.assertAlmostEqual(reciente.percentil(valores, 1), 4.0)

    def test_ignora_nulos(self):
        self.assertAlmostEqual(reciente.percentil([None, 2, 4], 0.5), 3.0)

    def test_sin_datos(self):
        self.assertIsNone(reciente.percentil([], 0.5))
        self.assertIsNone(reciente.percentil([None, None], 0.5))


class TestClimatologia(unittest.TestCase):
    def test_totales_mensuales(self):
        # 2020 es bisiesto: enero 31, febrero 29, marzo 31.
        datos = {"time": [], "precipitation_sum": [],
                 "temperature_2m_max": [], "temperature_2m_min": []}
        for mes, dias, lluvia in ((1, 31, 2.0), (2, 29, 1.0), (3, 31, 0.0)):
            for dia in range(1, dias + 1):
                datos["time"].append(f"2020-{mes:02d}-{dia:02d}")
                datos["precipitation_sum"].append(lluvia)
                datos["temperature_2m_max"].append(30.0)
                datos["temperature_2m_min"].append(20.0)

        climas = reciente.construir_climatologia(
            datos, 2020, 2020, incluir_temperatura=True
        )
        enero = climas["2020"]
        self.assertEqual(enero["lluvia_mm"][0], 62.0)   # 31 × 2 mm
        self.assertEqual(enero["lluvia_mm"][1], 29.0)   # 29 × 1 mm
        self.assertEqual(enero["lluvia_mm"][2], 0.0)    # mes seco: 0, no null
        self.assertEqual(enero["lluvia_mm"][3], None)   # abril no vino
        self.assertEqual(enero["t2m"][0], 25.0)         # media de 30 y 20
        self.assertNotIn("m1", enero)

    def test_mes_incompleto_es_nulo(self):
        datos = {"time": [], "precipitation_sum": []}
        for dia in range(1, 32):
            datos["time"].append(f"2020-01-{dia:02d}")
            datos["precipitation_sum"].append(1.0)
        datos["time"].pop()
        datos["precipitation_sum"].pop()
        climas = reciente.construir_climatologia(datos, 2020, 2020)
        self.assertIsNone(climas["2020"]["lluvia_mm"][0])


class TestNormalVentana(unittest.TestCase):
    def test_cruza_de_mes_con_pesos_a_mano(self):
        # Ventana 20 oct – 18 nov: 12 días de octubre y 18 de noviembre.
        # 310 × 12/31 = 120; 300 × 18/30 = 180 -> normal 300.0
        climas = {"2000": {"lluvia_mm": [10] * 9 + [310.0, 300.0, 10]}}
        inicio, fin = reciente.ventana(dt.date(2026, 11, 18))
        normal = reciente.normal_ventana(climas, inicio, fin)
        self.assertEqual(inicio, dt.date(2026, 10, 20))
        self.assertAlmostEqual(normal["lluvia_mm"], 300.0)

    def test_temperatura_ponderada(self):
        climas = {"2000": {"t2m": [20] * 9 + [26.0, 25.0, 20]}}
        inicio, fin = reciente.ventana(dt.date(2026, 11, 18))
        normal = reciente.normal_ventana_temperatura(climas, inicio, fin)
        # (26×12/31 + 25×18/30) / (12/31 + 18/30) = 25.39
        self.assertAlmostEqual(normal, 25.4)

    def test_sin_climatologia(self):
        inicio, fin = reciente.ventana(dt.date(2026, 11, 7))
        self.assertIsNone(reciente.normal_ventana({}, inicio, fin)["lluvia_mm"])
        self.assertIsNone(reciente.normal_ventana_temperatura({}, inicio, fin))


class TestBanda(unittest.TestCase):
    def test_30_anios(self):
        # Octubre completo: totales 100..129 (un año por valor).
        climas = {
            str(1991 + anio): {"lluvia_mm": [100.0 + anio] * 12}
            for anio in range(30)
        }
        inicio, fin = reciente.ventana(dt.date(2026, 10, 31))
        banda = reciente.banda_por_anio(climas, inicio, fin)
        # La ventana son 30 días de octubre (2–31), no el mes completo:
        # totales (100..129) × 30/31. P25 = 107.25 × 30/31.
        self.assertAlmostEqual(banda[0], 107.25 * 30 / 31)
        self.assertAlmostEqual(banda[1], 121.75 * 30 / 31)

    def test_pocos_anios(self):
        climas = {"1991": {"lluvia_mm": [10.0] * 12}}
        inicio, fin = reciente.ventana(dt.date(2026, 10, 31))
        self.assertIsNone(reciente.banda_por_anio(climas, inicio, fin))


class TestAnomalias(unittest.TestCase):
    def test_tres_tramos(self):
        self.assertEqual(
            reciente.anomalia_lluvia(10.0, 100.0, (50.0, 150.0))["estado"],
            "por_debajo",
        )
        self.assertEqual(
            reciente.anomalia_lluvia(100.0, 100.0, (50.0, 150.0))["estado"],
            "normal",
        )
        self.assertEqual(
            reciente.anomalia_lluvia(200.0, 100.0, (50.0, 150.0))["estado"],
            "por_encima",
        )

    def test_borde_de_la_banda_es_normal(self):
        self.assertEqual(
            reciente.anomalia_lluvia(50.0, 100.0, (50.0, 150.0))["estado"],
            "normal",
        )

    def test_porcentaje(self):
        self.assertEqual(reciente.anomalia_lluvia(10.0, 100.0, None)["pct"], -90)
        self.assertEqual(reciente.anomalia_lluvia(100.0, 100.0, None)["pct"], 0)
        self.assertEqual(reciente.anomalia_lluvia(200.0, 100.0, None)["pct"], 100)

    def test_normal_cero_no_divide(self):
        bloque = reciente.anomalia_lluvia(10.0, 0.0, None)
        self.assertIsNone(bloque["pct"])
        self.assertIsNone(bloque["estado"])

    def test_temperatura(self):
        bloque = reciente.anomalia_temperatura(25.5, 24.0, (24.0, 25.0))
        self.assertAlmostEqual(bloque["delta"], 1.5)
        self.assertEqual(bloque["estado"], "por_encima")


class TestHumedad(unittest.TestCase):
    def test_valor_y_cambio(self):
        inicio = dt.date(2026, 10, 1)
        datos = horario(inicio, 38, valor=0.30)
        # Los últimos 7 días completos a 0.40 y los 7 anteriores a 0.30.
        valores = datos["hourly"]["soil_moisture_0_to_7cm"]
        for indice in range(len(valores) - 7 * 24, len(valores)):
            valores[indice] = 0.40
        bloque = reciente.anomalia_humedad(
            valores, datos["hourly"]["time"], AHORA
        )
        self.assertAlmostEqual(bloque["valor"], 0.40)
        self.assertAlmostEqual(bloque["cambio_7d"], 0.10)
        self.assertIsNone(bloque["banda"])
        self.assertIn("0–7 cm", bloque["nota"])

    def test_sin_horas(self):
        bloque = reciente.anomalia_humedad([], [], AHORA)
        self.assertIsNone(bloque["valor"])
        self.assertIsNone(bloque["cambio_7d"])


class TestConstruirFinca(unittest.TestCase):
    def test_respuesta_completa(self):
        bloque = reciente.construir_finca(
            FINCA, respuesta_completa(), climatologia_simple(), AHORA
        )
        self.assertEqual(bloque["id"], "constanza")
        self.assertEqual(len(bloque["serie_30d"]), 30)
        self.assertEqual(bloque["serie_30d"][0]["fecha"], "2026-10-09")
        self.assertEqual(bloque["serie_30d"][-1]["fecha"], "2026-11-07")
        self.assertEqual(len(bloque["pronostico"]), 7)
        self.assertEqual(bloque["pronostico"][0]["fecha"], "2026-11-09")
        self.assertAlmostEqual(bloque["lluvia"]["30d_mm"], 30.0)
        self.assertEqual(bloque["lluvia"]["estado"], "por_encima")
        self.assertAlmostEqual(bloque["temperatura"]["media"], 25.0)
        self.assertAlmostEqual(bloque["humedad_superficial"]["valor"], 0.30)
        self.assertEqual(bloque["avisos"], [])

    def test_humedad_toda_nula(self):
        respuesta = respuesta_completa()
        respuesta["hourly"]["soil_moisture_0_to_7cm"] = [None] * len(
            respuesta["hourly"]["time"]
        )
        bloque = reciente.construir_finca(
            FINCA, respuesta, climatologia_simple(), AHORA
        )
        self.assertEqual(len(bloque["serie_30d"]), 30)
        self.assertTrue(all(fila["humedad"] is None for fila in bloque["serie_30d"]))
        self.assertIsNone(bloque["humedad_superficial"]["valor"])
        self.assertTrue(
            any("humedad superficial" in aviso for aviso in bloque["avisos"])
        )

    def test_sin_respuesta_es_nulo_y_avisa(self):
        bloque = reciente.construir_finca(
            FINCA, None, climatologia_simple(), AHORA
        )
        self.assertEqual(len(bloque["serie_30d"]), 30)
        self.assertTrue(all(fila["lluvia_mm"] is None for fila in bloque["serie_30d"]))
        self.assertEqual(bloque["pronostico"], [])
        self.assertIsNone(bloque["lluvia"]["30d_mm"])
        self.assertIsNotNone(bloque["lluvia"]["normal_mm"])
        self.assertTrue(bloque["avisos"])


class TestConstruirReciente(unittest.TestCase):
    def test_contrato(self):
        fincas = [
            dict(FINCA, id="constanza"),
            dict(FINCA, id="azua", nombre="Azua"),
            dict(FINCA, id="san_francisco_de_macoris", nombre="San Francisco de Macorís"),
        ]
        respuestas = {
            finca["id"]: respuesta_completa() for finca in fincas
        }
        climas = {finca["id"]: climatologia_simple() for finca in fincas}
        objeto = reciente.construir_reciente(fincas, respuestas, climas, AHORA)

        self.assertEqual(objeto["version"], 1)
        self.assertTrue(objeto["actualizado"].endswith("-04:00"))
        self.assertEqual(objeto["ventana"]["fin"], "2026-11-07")
        self.assertEqual(objeto["ventana"]["dias"], 30)
        self.assertTrue(objeto["fuente"]["no_nasa"])
        self.assertEqual(len(objeto["fincas"]), 3)
        for bloque in objeto["fincas"]:
            self.assertIn("lluvia", bloque)
            self.assertIn("temperatura", bloque)
            self.assertEqual(len(bloque["serie_30d"]), 30)
            self.assertIn(len(bloque["pronostico"]), (0, 7))
            self.assertIsNone(bloque["humedad_superficial"]["banda"])


class TestFrescura(unittest.TestCase):
    def test_hoy(self):
        resultado = reciente.evaluar_frescura("2026-11-08T09:00:00-04:00", AHORA)
        self.assertEqual(resultado, {"dias": 0, "aviso": None})

    def test_dos_dias(self):
        resultado = reciente.evaluar_frescura("2026-11-06T09:00:00-04:00", AHORA)
        self.assertEqual(resultado["dias"], 2)
        self.assertIsNone(resultado["aviso"])

    def test_seis_dias(self):
        resultado = reciente.evaluar_frescura("2026-11-02T09:00:00-04:00", AHORA)
        self.assertEqual(resultado["aviso"], "datos de hace 6 días")


class TestArchivos(unittest.TestCase):
    def test_cache_roto(self):
        carpeta = carpeta_temporal()
        try:
            ruta = os.path.join(carpeta, "reciente.json")
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write("{ roto")
            self.assertIsNone(reciente.leer_cache(ruta))
            self.assertIsNone(reciente.leer_cache(os.path.join(carpeta, "no.json")))
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    def test_escribir_atomico(self):
        carpeta = carpeta_temporal()
        try:
            ruta = os.path.join(carpeta, "salida", "reciente.json")
            reciente.escribir_atomico(ruta, {"version": 1, "texto": "m³/m³"})
            with open(ruta, encoding="utf-8") as archivo:
                self.assertEqual(json.load(archivo)["texto"], "m³/m³")
            self.assertFalse(os.path.exists(ruta + ".tmp"))
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
