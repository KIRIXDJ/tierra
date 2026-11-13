"""Pruebas del generador satelital de GIBS (sin red: funciones puras)."""

import math
import pathlib
import unittest

from PIL import Image

import generar_satelite as gs

RAIZ = pathlib.Path(__file__).resolve().parent.parent


class TestGeometria(unittest.TestCase):
    def test_tile_xy_origen(self):
        x, y = gs.tile_xy(0.0, 0.0, 0)
        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.5)

    def test_tile_xy_cuadrante(self):
        x, y = gs.tile_xy(18.91, -70.74, 9)
        self.assertTrue(0 < x < 2 ** 9)
        self.assertTrue(0 < y < 2 ** 9)
        self.assertLess(y, 256)          # hemisferio norte: mitad superior del mundo

    def test_resolucion(self):
        self.assertAlmostEqual(gs.resolucion_m(0, 0), 156543.0, places=0)
        self.assertAlmostEqual(gs.resolucion_m(9, 18.91), 289.2, places=1)


class TestColormap(unittest.TestCase):
    def test_parsea_rangos(self):
        xml = ('<ColorMap><Entries>'
               '<ColorMapEntry rgb="10,20,30" value="[0.1,0.2)"/>'
               '<ColorMapEntry rgb="40,50,60" value="[0.2,0.4)"/>'
               '</Entries></ColorMap>')
        mapa = gs.mapa_colores(xml)
        self.assertAlmostEqual(mapa[(10, 20, 30)], 0.15)
        self.assertAlmostEqual(mapa[(40, 50, 60)], 0.3)

    def test_rango_debajo_de_cero(self):
        xml = '<ColorMapEntry rgb="1,2,3" value="[-0.3,-0.2)"/>'
        self.assertAlmostEqual(gs.mapa_colores(xml)[(1, 2, 3)], -0.25)


class TestDecodificar(unittest.TestCase):
    def test_media_de_ventana(self):
        imagen = Image.new("RGBA", (5, 5), (10, 20, 30, 255))
        mapa = {(10, 20, 30): 0.5}
        salida = gs.decodificar_tile(imagen, 2, 2, 1, mapa)
        self.assertAlmostEqual(salida["valor"], 0.5)
        self.assertAlmostEqual(salida["cobertura"], 1.0)

    def test_transparentes_no_cuentan(self):
        imagen = Image.new("RGBA", (5, 5), (10, 20, 30, 0))
        salida = gs.decodificar_tile(imagen, 2, 2, 1, {(10, 20, 30): 0.5})
        self.assertIsNone(salida["valor"])
        self.assertEqual(salida["cobertura"], 0.0)


class TestCapacidades(unittest.TestCase):
    def test_fecha_por_defecto(self):
        xml = ('<Layer><ows:Identifier>MODIS_Terra_L3_NDVI_16Day</ows:Identifier>'
               '<Dimension><Default>2026-10-16</Default></Dimension></Layer>')
        self.assertEqual(
            gs.fecha_por_defecto(xml, "MODIS_Terra_L3_NDVI_16Day"), "2026-10-16")
        self.assertIsNone(gs.fecha_por_defecto(xml, "OTRA"))


class TestSnapshot(unittest.TestCase):
    def test_snapshot_existente(self):
        ruta = RAIZ / "datos" / "satelite.json"
        self.assertTrue(ruta.exists(), "falta datos/satelite.json")
        self.assertEqual(gs.revisar(), 0)
        datos = gs.json.loads(ruta.read_text(encoding="utf-8"))
        self.assertIn("ndvi", datos["capas"])
        self.assertIn("lluvia", datos["capas"])
        for capa in datos["capas"].values():
            self.assertTrue((RAIZ / "datos" / capa["imagen"]).exists())
            self.assertGreater(capa["resolucion_m"], 0)


if __name__ == "__main__":
    unittest.main()
