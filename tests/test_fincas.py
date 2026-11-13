"""Pruebas de la climatología mensual de las fincas piloto (sin red)."""

import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from generar_fincas import FINCAS, construir_finca
from tools import power_cliente
from tools.power_cliente import ErrorPower, descargar_mensual, parsear_mensual

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "fixtures" / "power_mensual.json"
PUBLICADO = RAIZ / "datos" / "fincas.json"
VARIABLES = ("PRECTOTCORR", "T2M")


def leer_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mensual_de_prueba(anio_ini=1991, anio_fin=2020):
    """Serie mensual completa con números inventados (no sale en la app)."""
    return {
        "PRECTOTCORR": {
            anio: {mes: 2.0 + mes / 10 for mes in range(1, 13)}
            for anio in range(anio_ini, anio_fin + 1)
        },
        "T2M": {
            anio: {mes: 20.0 + mes / 10 for mes in range(1, 13)}
            for anio in range(anio_ini, anio_fin + 1)
        },
    }


class Respuesta:
    def __init__(self, datos, status=200):
        self._datos = datos
        self.status_code = status

    def json(self):
        return self._datos


class TestParsearMensual(unittest.TestCase):
    def test_doce_meses_sin_anual(self):
        mensual = parsear_mensual(leer_fixture(), VARIABLES, 1991, 1991)
        self.assertEqual(set(mensual), set(VARIABLES))
        for variable in VARIABLES:
            meses = mensual[variable][1991]
            self.assertEqual(sorted(meses), list(range(1, 13)))
            self.assertTrue(all(isinstance(v, float) for v in meses.values()))

    def test_relleno_es_none(self):
        datos = leer_fixture()
        datos["properties"]["parameter"]["PRECTOTCORR"]["199107"] = -999.0
        mensual = parsear_mensual(datos, VARIABLES, 1991, 1991)
        self.assertIsNone(mensual["PRECTOTCORR"][1991][7])
        self.assertEqual(mensual["PRECTOTCORR"][1991][6], 1.25)


class TestDescargarMensual(unittest.TestCase):
    def test_anios_pelados_y_parametros(self):
        visto = {}

        def get(url, params=None, timeout=None):
            visto.update(params)
            return Respuesta(leer_fixture())

        with patch.object(power_cliente.requests, "get", side_effect=get):
            mensual = descargar_mensual(18.91, -70.74, VARIABLES, 1991, 2020)

        self.assertEqual(visto, {
            "parameters": "PRECTOTCORR,T2M",
            "community": "AG",
            "latitude": "18.9100",
            "longitude": "-70.7400",
            "start": "1991",
            "end": "2020",
            "format": "JSON",
        })
        # "199101" -> mes 1 y "199102" -> mes 2, sin corrimiento
        self.assertEqual(mensual["T2M"][1991][1], 18.19)
        self.assertEqual(mensual["T2M"][1991][2], 19.83)

    def test_error_http(self):
        with patch.object(power_cliente.requests, "get", return_value=Respuesta({}, 500)):
            with self.assertRaises(ErrorPower):
                descargar_mensual(0.0, 0.0, VARIABLES, 1991, 2020)


class TestConstruirFinca(unittest.TestCase):
    def test_treinta_anios_doce_meses(self):
        finca = construir_finca(FINCAS[0], mensual_de_prueba())
        self.assertEqual(finca["id"], "constanza")
        self.assertEqual(finca["zona_horaria"], "America/Santo_Domingo")
        self.assertEqual(finca["cultivo_actual"], "provisional")
        climatologia = finca["climatologia"]
        self.assertEqual(climatologia["periodo"], [1991, 2020])
        self.assertEqual(
            sorted(climatologia["mensual"]),
            [str(anio) for anio in range(1991, 2021)],
        )
        for valores in climatologia["mensual"].values():
            self.assertEqual(len(valores["lluvia_mm_dia"]), 12)
            self.assertEqual(len(valores["t2m"]), 12)
        self.assertAlmostEqual(
            climatologia["mensual"]["1991"]["lluvia_mm_dia"][0], 2.1
        )

    def test_no_toca_la_finca_base(self):
        base = FINCAS[0]
        construir_finca(base, mensual_de_prueba())
        self.assertNotIn("climatologia", base)


class TestJsonPublicado(unittest.TestCase):
    def test_fincas_json(self):
        if not PUBLICADO.exists():
            self.skipTest("datos/fincas.json todavía no se ha generado")

        datos = json.loads(PUBLICADO.read_text(encoding="utf-8"))
        self.assertEqual(datos["version"], 1)
        self.assertEqual(datos["periodo"], [1991, 2020])
        self.assertEqual(
            [finca["id"] for finca in datos["fincas"]],
            ["constanza", "azua", "san_francisco_de_macoris"],
        )
        for finca in datos["fincas"]:
            climatologia = finca["climatologia"]
            self.assertEqual(climatologia["periodo"], [1991, 2020])
            self.assertEqual(
                climatologia["fuente"], "NASA POWER (reanálisis MERRA-2)"
            )
            mensual = climatologia["mensual"]
            self.assertEqual(
                sorted(mensual), [str(anio) for anio in range(1991, 2021)]
            )
            for valores in mensual.values():
                self.assertEqual(len(valores["lluvia_mm_dia"]), 12)
                self.assertEqual(len(valores["t2m"]), 12)
                for numero in valores["lluvia_mm_dia"] + valores["t2m"]:
                    self.assertFalse(
                        numero is not None and math.isnan(numero),
                        "hay NaN en la climatología publicada",
                    )


if __name__ == "__main__":
    unittest.main()
