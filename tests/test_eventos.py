import unittest
from tools.eventos import celda_de, contar_eventos


class TestEventos(unittest.TestCase):
    def test_celda_de(self):
        self.assertEqual(celda_de(18.91, -70.74), (17.5, -72.5))
        self.assertEqual(celda_de(-0.2, 179.9), (-2.5, 177.5))

    def test_contar(self):
        eventos = [
            {"geometry": [{"type": "Point", "coordinates": [-70.7, 18.9]}]},
            {"geometry": [{"type": "Point", "coordinates": [-70.6, 18.8]}]},
            {"geometry": [{"type": "Point", "coordinates": [10.2, 23.3]}]},
        ]
        def falso(categoria, desde, hasta):
            return eventos if categoria == "wildfires" else []
        conteo = contar_eventos(descargar=falso)
        self.assertEqual(conteo[(17.5, -72.5)]["incendios"], 2)
        self.assertEqual(conteo[(22.5, 12.5)]["tormentas"], 0)
