"""Pruebas del generador de riesgos climáticos (sin red: funciones puras)."""

import pathlib
import unittest

import generar_riesgos as gr

RAIZ = pathlib.Path(__file__).resolve().parent.parent


class TestResumenDiario(unittest.TestCase):
    def test_cuenta_eventos_por_anio(self):
        parametros = {
            "PRECTOTCORR": {
                "20200101": 25.0, "20200102": 0.0, "20200103": 5.0,
                "20210101": 30.0, "20210102": 0.5,
            },
            "T2M_MAX": {"20200101": 36.0, "20200102": 30.0, "20210101": 35.5},
            "T2M_MIN": {"20200101": 1.5, "20200102": 10.0},
        }
        por_anio = gr.resumir_diario(parametros, 2020, 2021)
        self.assertEqual(por_anio[2020]["lluvia_20"], 1)
        self.assertEqual(por_anio[2020]["secos"], 1)
        self.assertEqual(por_anio[2020]["calor_35"], 1)
        self.assertEqual(por_anio[2020]["heladas"], 1)
        self.assertAlmostEqual(por_anio[2020]["lluvia_mm"], 30.0)
        self.assertAlmostEqual(por_anio[2020]["lluvia_max"], 25.0)
        self.assertEqual(por_anio[2021]["lluvia_20"], 1)
        self.assertEqual(por_anio[2021]["calor_35"], 1)

    def test_ignora_relleno_y_fechas_raras(self):
        parametros = {
            "PRECTOTCORR": {"20200101": -999.0, "2020": 3.0, "20200102": 2.0},
            "T2M_MAX": {}, "T2M_MIN": {},
        }
        por_anio = gr.resumir_diario(parametros, 2020, 2020)
        self.assertAlmostEqual(por_anio[2020]["lluvia_mm"], 2.0)


class TestResumenMensual(unittest.TestCase):
    def test_base_reciente_y_mes_13(self):
        parametros = {
            "GWETROOT": {"202001": 0.5, "202101": 0.7, "202113": 9.9},
            "EVLAND": {"202001": 1.0, "202101": 3.0},
        }
        resumen = gr.resumir_mensual(parametros, 2020, 2021)
        self.assertAlmostEqual(resumen["GWETROOT"]["base"], 0.5)
        self.assertAlmostEqual(resumen["GWETROOT"]["reciente"], 0.7)
        self.assertAlmostEqual(resumen["EVLAND"]["reciente"], 3.0)
        self.assertEqual(resumen["GWETROOT"]["unidad"], "0-1")


class TestResumenAnual(unittest.TestCase):
    def test_compara_base_con_reciente(self):
        por_anio = {anio: {"calor_35": 1, "lluvia_20": 2, "secos": 100,
                           "heladas": 0, "lluvia_mm": 1000, "lluvia_max": 20}
                    for anio in range(1991, 2026)}
        por_anio[2021]["lluvia_20"] = 10
        resumen = gr.resumir_anual(por_anio)
        self.assertAlmostEqual(resumen["lluvia_20"]["base"], 2.0)
        self.assertGreater(resumen["lluvia_20"]["reciente"], 2.0)
        self.assertEqual(resumen["heladas"]["reciente"], 0)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_existente_es_valido(self):
        ruta = RAIZ / "datos" / "riesgos.json"
        self.assertTrue(ruta.exists(), "falta datos/riesgos.json")
        self.assertEqual(gr.revisar(), 0)


if __name__ == "__main__":
    unittest.main()
