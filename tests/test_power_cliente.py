import unittest
from unittest.mock import patch

from tools import power_cliente
from tools.power_cliente import ErrorPower, descargar_celda


class Respuesta:
    def __init__(self, datos, status=200):
        self._datos = datos
        self.status_code = status

    def json(self):
        return self._datos


def payload(anios, t2m=None):
    valores = {f"{a}13": (t2m or {}).get(a, 20.0) for a in anios}
    valores[f"{anios[0]}01"] = 99.0  # un mes: debe ignorarse
    return {"properties": {"parameter": {"T2M": valores}}}


class TestDescargarCelda(unittest.TestCase):
    def test_anuales_y_relleno(self):
        anios = list(range(1984, 2026))
        datos = payload(anios, {1984: -999.0})
        with patch.object(power_cliente.requests, "get", return_value=Respuesta(datos)):
            serie = descargar_celda(17.5, -72.5, ["T2M"])
        self.assertEqual(len(serie["T2M"]), 42)
        self.assertIsNone(serie["T2M"][0])
        self.assertEqual(serie["T2M"][1], 20.0)

    def test_error_http(self):
        with patch.object(power_cliente.requests, "get", return_value=Respuesta({}, 500)):
            with self.assertRaises(ErrorPower):
                descargar_celda(0.0, 0.0, ["T2M"], 2000, 2001)

    def test_timeout(self):
        import requests as rq
        with patch.object(power_cliente.requests, "get", side_effect=rq.Timeout()):
            with self.assertRaises(ErrorPower):
                descargar_celda(0.0, 0.0, ["T2M"])
