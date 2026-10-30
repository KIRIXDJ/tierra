import unittest
from tools.malla_global import centros, construir_malla


class TestMalla(unittest.TestCase):
    def test_centros_res90(self):
        puntos = centros(90)
        self.assertEqual(len(puntos), 8)  # 2 latitudes x 4 longitudes
        self.assertEqual(puntos[0], (-45.0, -135.0))

    def test_construir_malla_sintetica(self):
        def falso(lat, lon, variables, anio_ini, anio_fin):
            anios = list(range(anio_ini, anio_fin + 1))
            serie = [float(i) for i in range(len(anios))]
            if lat < 0:
                serie = [float(-i) for i in range(len(anios))]
            return {v: serie for v in variables}

        malla = construir_malla(res=90, descargar=falso)
        self.assertEqual(len(malla["celdas"]), 8)
        self.assertEqual(malla["res"], 90)
        primera = malla["celdas"][0]
        self.assertEqual(primera[0], -45.0)
        self.assertLess(primera[2], 0)  # pendiente negativa en el sur
        self.assertEqual(len(primera), 16)
        self.assertEqual(primera[14], 0)  # incendios

    def test_serie_corta_es_nula(self):
        def corto(lat, lon, variables, anio_ini, anio_fin):
            return {v: [10.0] * 20 + [None] * 22 for v in variables}
        malla = construir_malla(res=90, descargar=corto)
        self.assertIsNone(malla["celdas"][0][2])
        self.assertIsNone(malla["celdas"][0][3])
