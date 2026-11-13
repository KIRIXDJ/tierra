import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generar_rotaciones

from tools.rotaciones import (
    CULTIVOS_PROVISIONALES,
    evaluar_rotaciones,
    meses_secos,
)

from generar_rotaciones import construir


def clima(secos=(2, 3, 4), anios=("1991", "1992", "1993")):
    """Climatología sintética: los meses de ``secos`` llueven 1 mm/día."""
    mensual = {}
    for anio in anios:
        lluvia = [1.0 if mes in secos else 10.0 for mes in range(1, 13)]
        mensual[anio] = {"lluvia_mm_dia": lluvia, "t2m": [24.0] * 12}
    return {
        "periodo": [1991, 2020],
        "fuente": "NASA POWER (reanálisis MERRA-2)",
        "mensual": mensual,
    }


def finca(cultivo_actual="maiz", secos=(2, 3, 4)):
    return {
        "id": "constanza",
        "nombre": "Constanza",
        "cultivo_actual": cultivo_actual,
        "climatologia": clima(secos),
    }


def tabla():
    """Tres cultivos de prueba con demanda y meses controlados."""
    return {
        "seco": {
            "id": "seco",
            "nombre": "Seco",
            "demanda_agua": "alta",
            "meses_criticos": [2, 3, 4],
            "estado": "provisional",
            "fuente": None,
        },
        "lluvioso": {
            "id": "lluvioso",
            "nombre": "Lluvioso",
            "demanda_agua": "alta",
            "meses_criticos": [9, 10, 11],
            "estado": "provisional",
            "fuente": None,
        },
        "bajo": {
            "id": "bajo",
            "nombre": "Bajo",
            "demanda_agua": "baja",
            "meses_criticos": [9, 10, 11],
            "estado": "provisional",
            "fuente": None,
        },
    }


class TestMesesSecos(unittest.TestCase):
    def test_climatologia_sintetica_conocida(self):
        self.assertEqual(meses_secos(clima((2, 3, 4))), [2, 3, 4])
        self.assertEqual(meses_secos(clima((6, 7, 8))), [6, 7, 8])

    def test_acepta_el_bloque_mensual_directo(self):
        self.assertEqual(meses_secos(clima((1, 5, 12))["mensual"]), [1, 5, 12])

    def test_ignora_huecos(self):
        datos = clima((2, 3, 4))
        datos["mensual"]["1991"]["lluvia_mm_dia"][1] = None
        self.assertEqual(meses_secos(datos), [2, 3, 4])

    def test_sin_climatologia(self):
        self.assertEqual(meses_secos(None), [])
        self.assertEqual(meses_secos({}), [])
        self.assertEqual(meses_secos({"mensual": {}}), [])


class TestEstrategias(unittest.TestCase):
    def test_tres_estrategias_ids_unicos_y_rango(self):
        resultado = evaluar_rotaciones(finca())
        self.assertEqual(resultado["id"], "constanza")
        self.assertEqual(len(resultado["meses_secos"]), 3)

        estrategias = resultado["estrategias"]
        self.assertEqual(len(estrategias), 3)
        self.assertEqual(
            [estrategia["id"] for estrategia in estrategias],
            ["actual", "alternativa_1", "alternativa_2"],
        )
        self.assertEqual(len({estrategia["id"] for estrategia in estrategias}), 3)

        for estrategia in estrategias:
            self.assertGreaterEqual(estrategia["indice"], 0)
            self.assertLessEqual(estrategia["indice"], 100)
            self.assertIn(estrategia["demanda_agua"], ("alta", "media", "baja"))
            self.assertTrue(
                all(1 <= mes <= 12 for mes in estrategia["meses_criticos"])
            )
            self.assertEqual(
                set(estrategia["componentes"]), {"agua", "diversidad"}
            )
            agua = estrategia["componentes"]["agua"]
            diversidad = estrategia["componentes"]["diversidad"]
            self.assertEqual(
                estrategia["indice"],
                int(agua * 5 + diversidad * 5 + 0.5),
            )

    def test_agua_baja_cuando_los_criticos_caen_en_los_secos(self):
        seco = evaluar_rotaciones(
            finca("seco"), cultivos=tabla()
        )["estrategias"][0]
        lluvioso = evaluar_rotaciones(
            finca("lluvioso"), cultivos=tabla()
        )["estrategias"][0]

        self.assertEqual(seco["componentes"]["agua"], 2.5)
        self.assertEqual(lluvioso["componentes"]["agua"], 10.0)
        self.assertLess(seco["indice"], lluvioso["indice"])

    def test_contexto_seco_resta_exactamente_15_a_demanda_alta(self):
        contexto = {"lluvia": {"estado": "por_debajo"}}
        sin = evaluar_rotaciones(
            finca("lluvioso"), cultivos=tabla()
        )["estrategias"][0]
        con = evaluar_rotaciones(
            finca("lluvioso"), contexto_reciente=contexto, cultivos=tabla()
        )["estrategias"][0]

        self.assertEqual(con["demanda_agua"], "alta")
        self.assertEqual(sin["indice"] - con["indice"], 15)
        self.assertTrue(any("15" in motivo for motivo in con["motivos"]))

    def test_contexto_seco_no_cambia_demanda_baja(self):
        contexto = {"lluvia": {"estado": "por_debajo"}}
        sin = evaluar_rotaciones(
            finca("bajo"), cultivos=tabla()
        )["estrategias"][0]
        con = evaluar_rotaciones(
            finca("bajo"), contexto_reciente=contexto, cultivos=tabla()
        )["estrategias"][0]

        self.assertEqual(con["demanda_agua"], "baja")
        self.assertEqual(sin["indice"], con["indice"])

    def test_riesgos_y_datos_faltantes_no_vacios(self):
        for estrategia in evaluar_rotaciones(finca())["estrategias"]:
            self.assertTrue(estrategia["riesgos"])
            self.assertTrue(estrategia["datos_faltantes"])

    def test_provisional_mientras_no_haya_fuentes(self):
        for estrategia in evaluar_rotaciones(finca())["estrategias"]:
            self.assertTrue(estrategia["provisional"])
            self.assertEqual(estrategia["fuentes"], [])

    def test_con_fuente_deja_de_ser_provisional(self):
        cultivos = {
            "maiz": {
                "id": "maiz",
                "nombre": "Maíz",
                "demanda_agua": "alta",
                "meses_criticos": [5, 6, 7, 8],
                "estado": "revisado",
                "fuente": "FAO",
            }
        }
        estrategia = evaluar_rotaciones(
            finca("maiz"), cultivos=cultivos
        )["estrategias"][0]

        self.assertFalse(estrategia["provisional"])
        self.assertEqual(estrategia["fuentes"], ["FAO"])

    def test_sin_climatologia_avisa(self):
        datos = finca()
        del datos["climatologia"]
        resultado = evaluar_rotaciones(datos)

        self.assertEqual(resultado["meses_secos"], [])
        for estrategia in resultado["estrategias"]:
            faltantes = " ".join(estrategia["datos_faltantes"])
            self.assertIn("sin climatología POWER", faltantes)

    def test_tabla_inline_es_provisional(self):
        self.assertTrue(CULTIVOS_PROVISIONALES)
        for cultivo in CULTIVOS_PROVISIONALES.values():
            self.assertEqual(cultivo["estado"], "provisional")
            self.assertIsNone(cultivo["fuente"])


class TestConstruir(unittest.TestCase):
    def test_documento_con_tres_fincas(self):
        fincas = [
            finca(),
            dict(finca(), id="azua"),
            dict(finca(), id="san_francisco_de_macoris"),
        ]
        documento = construir({"fincas": fincas})

        self.assertEqual(documento["version"], 1)
        self.assertEqual(
            documento["fuente_clima"], "NASA POWER (reanálisis MERRA-2)"
        )
        self.assertEqual(len(documento["fincas"]), 3)
        for bloque in documento["fincas"]:
            self.assertEqual(len(bloque["meses_secos"]), 3)
            self.assertEqual(len(bloque["estrategias"]), 3)

    def test_reciente_aplica_por_id(self):
        cultivos = {"cultivos": list(tabla().values())}
        reciente = {
            "fincas": [
                {"id": "constanza", "lluvia": {"estado": "por_debajo"}}
            ]
        }
        sin = construir(
            {"fincas": [finca("lluvioso")]},
            cultivos_documento=cultivos,
        )["fincas"][0]["estrategias"][0]
        con = construir(
            {"fincas": [finca("lluvioso")]},
            reciente_documento=reciente,
            cultivos_documento=cultivos,
        )["fincas"][0]["estrategias"][0]

        self.assertEqual(sin["indice"] - con["indice"], 15)


class TestGenerador(unittest.TestCase):
    def test_sin_fincas_devuelve_codigo_2(self):
        with patch.object(
            generar_rotaciones, "FINCAS", Path("no-existe-fincas.json")
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                codigo = generar_rotaciones.main(["--verificar"])
        self.assertEqual(codigo, 2)

    def test_escribe_json_y_js(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            fincas = raiz / "fincas.json"
            fincas.write_text(
                json.dumps({"fincas": [finca()]}), encoding="utf-8"
            )
            salida_json = raiz / "rotaciones.json"
            salida_js = raiz / "rotaciones.js"

            with patch.object(generar_rotaciones, "FINCAS", fincas), \
                    patch.object(
                        generar_rotaciones, "RECIENTE", raiz / "reciente.json"
                    ), \
                    patch.object(
                        generar_rotaciones, "CULTIVOS", raiz / "cultivos.json"
                    ), \
                    patch.object(generar_rotaciones, "SALIDA_JSON", salida_json), \
                    patch.object(generar_rotaciones, "SALIDA_JS", salida_js), \
                    patch.object(generar_rotaciones, "RAIZ", raiz), \
                    contextlib.redirect_stdout(io.StringIO()):
                codigo = generar_rotaciones.main([])

            self.assertEqual(codigo, 0)
            documento = json.loads(salida_json.read_text(encoding="utf-8"))
            self.assertEqual(len(documento["fincas"]), 1)
            self.assertEqual(len(documento["fincas"][0]["estrategias"]), 3)

            js = salida_js.read_text(encoding="utf-8")
            self.assertTrue(js.startswith("window.__ROTACIONES__ = "))
            self.assertTrue(js.rstrip().endswith(";"))


if __name__ == "__main__":
    unittest.main()


class TestSuelo(unittest.TestCase):
    """El suelo de ISRIC entra en el índice, marcado como heurística."""

    def _finca(self):
        return {"id": "constanza", "cultivo_actual": "maiz", "climatologia": {
            "periodo": [1991, 2020],
            "mensual": {str(anio): {"lluvia_mm_dia": [12, 9, 6, 8, 14, 20, 18, 17, 15, 13, 12, 11],
                                    "t2m": [22] * 12} for anio in range(1991, 2021)},
        }}

    def test_suelo_arcilloso_sube_el_agua(self):
        sin = evaluar_rotaciones(self._finca())
        con = evaluar_rotaciones(self._finca(), suelo={"arcilla_pct": 45.7})
        agua_sin = sin["estrategias"][0]["componentes"]["agua"]
        agua_con = con["estrategias"][0]["componentes"]["agua"]
        self.assertGreaterEqual(agua_con, agua_sin)
        self.assertTrue(any("arcilloso" in motivo for motivo in con["estrategias"][0]["motivos"]))
        self.assertTrue(any("drenaje" in riesgo for riesgo in con["estrategias"][0]["riesgos"]))

    def test_suelo_arenoso_o_sin_dato_no_cambia(self):
        base = evaluar_rotaciones(self._finca())
        arenoso = evaluar_rotaciones(self._finca(), suelo={"arcilla_pct": 10})
        self.assertEqual([e["indice"] for e in base["estrategias"]],
                         [e["indice"] for e in arenoso["estrategias"]])
        vacio = evaluar_rotaciones(self._finca(), suelo={"arcilla_pct": None})
        self.assertEqual([e["indice"] for e in base["estrategias"]],
                         [e["indice"] for e in vacio["estrategias"]])
