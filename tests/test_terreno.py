"""Pruebas del terreno SRTM (sin red: funciones puras y snapshot)."""

import pathlib
import unittest

import generar_terreno as gt

RAIZ = pathlib.Path(__file__).resolve().parent.parent


class TestElevacion(unittest.TestCase):
    def test_decodifica_terrarium(self):
        # 132*256 + 155 + 41/256 - 32768 ≈ 1179,16 m
        self.assertAlmostEqual(gt.decodificar_elevacion((132, 155, 41)), 1179.16, places=2)

    def test_altura_cero(self):
        self.assertAlmostEqual(gt.decodificar_elevacion((128, 0, 0)), 0.0)


class TestPendiente(unittest.TestCase):
    def test_plano_es_cero(self):
        plano = [[100] * 5 for _ in range(5)]
        valores = [v for fila in gt.pendientes(plano, 9.0) for v in fila]
        self.assertEqual(max(valores), 0.0)

    def test_rampa_de_45_grados(self):
        # 9 m de desnivel por cada píxel de 9 m → 45°
        rampa = [[fila * 9 for fila in range(5)] for _ in range(5)]
        valores = [v for fila in gt.pendientes(rampa, 9.0) for v in fila]
        self.assertAlmostEqual(max(valores), 45.0, places=1)

    def test_resumen(self):
        plano = [[1200] * 4 for _ in range(4)]
        datos = gt.resumen(plano, 9.0)
        self.assertEqual(datos["elevacion_media_m"], 1200)
        self.assertEqual(datos["pendiente_media_deg"], 0.0)
        self.assertEqual(datos["pendiente_alta_pct"], 0.0)
        self.assertEqual(datos["umbral_pendiente_deg"], 15.0)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_existente(self):
        ruta = RAIZ / "datos" / "terreno.json"
        self.assertTrue(ruta.exists(), "falta datos/terreno.json")
        self.assertEqual(gt.revisar(), 0)
        self.assertIn("SRTM", gt.json.loads(ruta.read_text(encoding="utf-8"))["fuente"])


if __name__ == "__main__":
    unittest.main()
