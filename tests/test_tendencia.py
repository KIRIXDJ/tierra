import unittest
from tools.tendencia import sen, mann_kendall, pendiente_decada


class TestSen(unittest.TestCase):
    def test_recta(self):
        self.assertAlmostEqual(sen([1, 2, 3, 4, 5]), 1.0)

    def test_recta_negativa(self):
        self.assertAlmostEqual(sen([5, 4, 3, 2, 1]), -1.0)

    def test_mediana_de_pendientes(self):
        # pendientes por pares: 1, 1, 1, 1, 10 -> mediana 1
        self.assertAlmostEqual(sen([0, 1, 2, 3, 4, 14]), 1.0)

    def test_pocos_datos(self):
        self.assertIsNone(sen([1, 2]))
        self.assertIsNone(sen([]))

    def test_por_decada(self):
        self.assertAlmostEqual(pendiente_decada([0, 1, 2, 3, 4, 5]), 10.0)


class TestMannKendall(unittest.TestCase):
    def test_tendencia_fuerte(self):
        z, p = mann_kendall(list(range(42)))
        self.assertGreater(z, 0)
        self.assertLess(p, 0.001)

    def test_sin_tendencia(self):
        z, p = mann_kendall([1, 2] * 21)
        self.assertGreater(p, 0.5)

    def test_empates(self):
        z, p = mann_kendall([5] * 42)
        self.assertEqual(z, 0.0)
        self.assertAlmostEqual(p, 1.0)

    def test_pocos_datos(self):
        self.assertIsNone(mann_kendall(list(range(9))))
