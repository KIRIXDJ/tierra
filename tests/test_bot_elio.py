"""Pruebas del bot real de Telegram de Elio (sin red: el HTTP se inyecta)."""

import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from tools import bot_elio

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TOKEN_FALSO = "123456:secreto-de-prueba"


class Respuesta:
    def __init__(self, datos, status=200):
        self._datos = datos
        self.status_code = status

    def json(self):
        return self._datos


class ClienteIA:
    """Cliente HTTP falso para DeepSeek: guarda la llamada y devuelve un texto."""

    def __init__(self, contenido="Follaje mayormente verde.", falla=False):
        self.contenido = contenido
        self.falla = falla
        self.llamadas = []

    def post(self, url, headers=None, json=None, timeout=None):
        if self.falla:
            raise RuntimeError("sin red")
        self.llamadas.append({"url": url, "headers": headers or {},
                              "cuerpo": json or {}, "timeout": timeout})
        return Respuesta({"choices": [{"message": {"content": self.contenido}}]})


class ClienteTelegram:
    """Cliente falso de Telegram: apunta los envíos y contesta ok."""

    def __init__(self, actualizaciones=None):
        self.actualizaciones = actualizaciones or []
        self.envios = []

    def post(self, url, data=None, files=None, timeout=None):
        self.envios.append({"url": url, "datos": data or {}, "archivos": files})
        if url.endswith("/getUpdates"):
            return Respuesta({"ok": True, "result": self.actualizaciones})
        return Respuesta({"ok": True, "result": {"username": "climaxeliobot"}})


class ClienteCorta(ClienteTelegram):
    """Devuelve un getUpdates vacío y corta el bucle con Ctrl+C en el siguiente."""

    def __init__(self):
        super().__init__()
        self.veces = 0

    def post(self, url, data=None, files=None, timeout=None):
        if url.endswith("/getUpdates"):
            self.veces += 1
            if self.veces > 1:
                raise KeyboardInterrupt
            return Respuesta({"ok": True, "result": []})
        return super().post(url, data=data, files=files, timeout=timeout)


def contexto():
    return bot_elio.construir_contexto(bot_elio.cargar_datos())


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexto = contexto()

    def setUp(self):
        # Estado fresco por prueba: varias lo mutan a propósito.
        self.estado = bot_elio.estado_vacio(self.contexto)

    def interpretar(self, texto, estado=None):
        return bot_elio.interpretar_comando(
            texto, estado if estado is not None else self.estado, self.contexto)


class TestContexto(Base):
    def test_claves_del_contexto(self):
        for clave in ("finca", "finca_nombre", "parcelas", "mapa", "clima_reciente",
                      "fincas_power", "rotaciones", "suelo", "fuentes"):
            self.assertIn(clave, self.contexto)
        self.assertEqual([p["id"] for p in self.contexto["parcelas"]],
                         ["la-esperanza", "el-hoyo", "la-loma"])
        self.assertTrue(self.contexto["clima_reciente"]["fincas"])
        self.assertTrue(self.contexto["fincas_power"])
        self.assertTrue(self.contexto["rotaciones"]["fincas"])
        self.assertTrue(self.contexto["suelo"]["fincas"])

    def test_contexto_sin_urls(self):
        # El contrato prohíbe inventar URLs: el contexto no lleva ninguna.
        self.assertNotIn("http", json.dumps(self.contexto, ensure_ascii=False))

    def test_prompt_sistema_contrato(self):
        self.assertIn("No tengo ese dato.", bot_elio.PROMPT_SISTEMA)
        self.assertIn("3 frases", bot_elio.PROMPT_SISTEMA)
        self.assertIn("Español", bot_elio.PROMPT_SISTEMA)


class TestEstado(Base):
    def test_estado_vacio_sigue_el_contrato(self):
        self.assertEqual(self.estado["version"], 1)
        self.assertEqual(self.estado["origen"], "telegram")
        self.assertEqual(self.estado["modo"], "comandos")
        self.assertEqual(set(self.estado["parcelas"]),
                         {"la-esperanza", "el-hoyo", "la-loma"})
        for valores in self.estado["parcelas"].values():
            self.assertEqual(set(valores), {"riego", "techo", "ventilacion"})
            self.assertTrue(all(valor is False for valor in valores.values()))
        self.assertIn("historial", self.estado)

    def test_estado_inexistente_no_rompe(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            estado = bot_elio.cargar_estado(self.contexto, ruta)
        self.assertEqual(set(estado["parcelas"]), {"la-esperanza", "el-hoyo", "la-loma"})

    def test_estado_roto_tambien_cae_en_vacio(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            ruta.write_text("{no es json", encoding="utf-8")
            estado = bot_elio.cargar_estado(self.contexto, ruta)
        self.assertIs(estado["parcelas"]["el-hoyo"]["riego"], False)

    def test_estado_previo_se_conserva(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            guardado = bot_elio.estado_vacio(self.contexto)
            guardado["parcelas"]["el-hoyo"]["riego"] = True
            ruta.write_text(json.dumps(guardado), encoding="utf-8")
            estado = bot_elio.cargar_estado(self.contexto, ruta)
        self.assertIs(estado["parcelas"]["el-hoyo"]["riego"], True)

    def test_escritura_atomica_deja_json_valido(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            bot_elio.aplicar_cambios(self.estado, {"la-loma": {"techo": True}})
            bot_elio.registrar(self.estado, "/techo on", "Techo cerrado.", "comandos")
            bot_elio.guardar_estado(self.estado, ruta)
            leido = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertIs(leido["parcelas"]["la-loma"]["techo"], True)
            self.assertIn("actualizado", leido)
            self.assertEqual(len(leido["ultimo"]), 3)
            self.assertEqual(list(pathlib.Path(carpeta).glob("*.tmp")), [])
            self.assertEqual(ruta.read_text(encoding="utf-8")[-1], "\n")

    def test_historial_se_recorta(self):
        estado = bot_elio.estado_vacio(self.contexto)
        for numero in range(25):
            bot_elio.registrar(estado, f"/estado {numero}", f"respuesta {numero}", "comandos")
        self.assertEqual(len(estado["historial"]), bot_elio.MAX_HISTORIAL)
        self.assertEqual(estado["historial"][-1]["texto"], "/estado 24")
        self.assertEqual(estado["ultimo"]["texto"], "/estado 24")

    def test_estado_vive_en_datos(self):
        self.assertEqual(bot_elio.ESTADO, bot_elio.DATOS / "estado_finca.json")


class TestComandos(Base):
    def test_ayuda_lista_comandos(self):
        respuesta = self.interpretar("/ayuda")["respuesta"]
        for comando in ("/estado", "/parcelas", "/clima", "/rotaciones", "/riego",
                        "/techo", "/ventilar", "/foto", "/ayuda"):
            self.assertIn(comando, respuesta)
        self.assertIn("todas", respuesta)

    def test_parcelas(self):
        respuesta = self.interpretar("/parcelas")["respuesta"]
        for pid in ("la-esperanza", "el-hoyo", "la-loma"):
            self.assertIn(pid, respuesta)
        self.assertIn("Constanza", respuesta)

    def test_estado_muestra_actuadores(self):
        estado = bot_elio.estado_vacio(self.contexto)
        estado["parcelas"]["la-esperanza"]["riego"] = True
        respuesta = self.interpretar("/estado", estado)["respuesta"]
        self.assertIn("La Esperanza", respuesta)
        self.assertIn("Riego encendido", respuesta)
        self.assertIn("techo abierto", respuesta)

    def test_comando_invalido(self):
        orden = self.interpretar("/inventado")
        self.assertIn("No entiendo", orden["respuesta"])
        self.assertEqual(orden["cambios"], {})

    def test_clima_cita_fuente_sin_urls(self):
        respuesta = self.interpretar("/clima")["respuesta"]
        self.assertIn("Open-Meteo", respuesta)
        self.assertIn("no NASA", respuesta)
        self.assertIn("126.8", respuesta)          # lluvia real de 30 días de Constanza
        self.assertNotIn("http", respuesta)

    def test_riesgos_cita_power(self):
        respuesta = self.interpretar("/riesgos")["respuesta"]
        self.assertIn("NASA POWER", respuesta)
        self.assertIn("lluvia ≥ 20 mm", respuesta)
        self.assertIn("suelo de raíz", respuesta)
        self.assertIn("MERRA-2", respuesta)
        self.assertNotIn("http", respuesta)

    def test_contexto_incluye_riesgos(self):
        self.assertTrue(self.contexto["riesgos_power"]["fincas"])
        self.assertEqual(len(self.contexto["riesgos_power"]["fincas"]), 3)
        self.assertTrue(all("calor_35_dias_anio" in f
                            for f in self.contexto["riesgos_power"]["fincas"]))

    def test_rotaciones_cita_fuentes(self):
        respuesta = self.interpretar("/rotaciones")["respuesta"]
        self.assertIn("POWER", respuesta)
        self.assertIn("SoilGrids", respuesta)
        self.assertIn("No es recomendación agronómica", respuesta)

    def test_riego_on(self):
        orden = self.interpretar("/riego on")
        self.assertEqual(orden["cambios"], {"la-esperanza": {"riego": True}})
        self.assertIn("Riego encendido", orden["respuesta"])

    def test_riego_off_y_auto(self):
        self.assertEqual(self.interpretar("/riego off")["cambios"],
                         {"la-esperanza": {"riego": False}})
        orden = self.interpretar("/techo auto")
        self.assertEqual(orden["cambios"], {"la-esperanza": {"techo": False}})
        self.assertIn("automático", orden["respuesta"])

    def test_actuador_sin_valor(self):
        orden = self.interpretar("/riego")
        self.assertIn("Usa /riego on|off|auto", orden["respuesta"])
        self.assertEqual(orden["cambios"], {})

    def test_ventilar_solo_on_off(self):
        self.assertEqual(self.interpretar("/ventilar on")["cambios"],
                         {"la-esperanza": {"ventilacion": True}})
        orden = self.interpretar("/ventilar auto")
        self.assertEqual(orden["cambios"], {})
        self.assertIn("solo acepta on u off", orden["respuesta"])

    def test_parcela_por_nombre_y_por_id(self):
        por_nombre = self.interpretar("/riego on El Hoyo")["cambios"]
        por_id = self.interpretar("/riego on el-hoyo")["cambios"]
        self.assertEqual(por_nombre, {"el-hoyo": {"riego": True}})
        self.assertEqual(por_id, por_nombre)
        # las tildes y mayúsculas no importan
        self.assertEqual(self.interpretar("/techo on LA LOMA")["cambios"],
                         {"la-loma": {"techo": True}})

    def test_todas_las_parcelas(self):
        orden = self.interpretar("/techo on todas")
        self.assertEqual(set(orden["cambios"]), {"la-esperanza", "el-hoyo", "la-loma"})
        self.assertTrue(all(v == {"techo": True} for v in orden["cambios"].values()))

    def test_parcela_desconocida(self):
        orden = self.interpretar("/riego on la-quinta")
        self.assertIn("No conozco la parcela", orden["respuesta"])
        self.assertEqual(orden["cambios"], {})

    def test_interpretar_es_puro(self):
        estado = bot_elio.estado_vacio(self.contexto)
        self.interpretar("/riego on", estado)
        self.assertIs(estado["parcelas"]["la-esperanza"]["riego"], False)

    def test_texto_libre_va_a_la_ia(self):
        orden = self.interpretar("¿Va a llover esta semana?")
        self.assertEqual(orden["api"], "¿Va a llover esta semana?")
        self.assertIsNone(orden["respuesta"])

    def test_ia_forzada(self):
        self.assertEqual(self.interpretar("/ia ¿cómo va la finca?")["api"],
                         "¿cómo va la finca?")

    def test_foto_pie_menciona_esri(self):
        orden = self.interpretar("/foto")
        self.assertEqual(orden["foto"], "la-esperanza")
        self.assertIn("Esri", orden["respuesta"])
        self.assertIn("no NASA", orden["respuesta"])
        self.assertIn("simulad", orden["respuesta"])

    def test_foto_recorta_la_imagen(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("sin Pillow")
        recorte = bot_elio.recortar_parcela(
            self.contexto["parcelas"][0], self.contexto["mapa"])
        self.assertIsNotNone(recorte)
        self.assertTrue(recorte.startswith(b"\xff\xd8"))  # JPEG
        self.assertGreater(len(recorte), 1000)


class TestIA(Base):
    def test_sin_clave_responde_en_una_frase(self):
        respuesta = bot_elio.responder_api("¿va a llover?", self.contexto, clave=None)
        self.assertIn("DEEPSEEK_API_KEY", respuesta)
        self.assertNotIn("http", respuesta)

    def test_contrato_de_llamada(self):
        cliente = ClienteIA()
        respuesta = bot_elio.responder_api(
            "¿cómo va el clima?", self.contexto, clave="clave-falsa", cliente=cliente)
        self.assertEqual(respuesta, "Follaje mayormente verde.")
        llamada = cliente.llamadas[0]
        self.assertEqual(llamada["url"], bot_elio.API_IA)
        self.assertIn("clave-falsa", llamada["headers"]["Authorization"])
        cuerpo = llamada["cuerpo"]
        self.assertEqual(cuerpo["model"], "deepseek-chat")
        self.assertEqual(cuerpo["temperature"], 0.2)
        self.assertEqual(cuerpo["max_tokens"], 300)
        system, usuario = cuerpo["messages"][0], cuerpo["messages"][1]
        self.assertEqual(system["role"], "system")
        self.assertIn("No tengo ese dato.", system["content"])
        self.assertIn("Contexto:", usuario["content"])
        self.assertIn("Pregunta: ¿cómo va el clima?", usuario["content"])
        self.assertIn("la-esperanza", usuario["content"])

    def test_fallo_de_red_no_rompe(self):
        respuesta = bot_elio.responder_api(
            "¿va a llover?", self.contexto, clave="clave-falsa",
            cliente=ClienteIA(falla=True))
        self.assertIn("No pude consultar la IA", respuesta)
        self.assertNotIn("Traceback", respuesta)

    def test_sin_clave_menciona_las_dos_variables(self):
        respuesta = bot_elio.responder_api("¿va a llover?", self.contexto, clave=None)
        self.assertIn("IA_API_KEY", respuesta)
        self.assertIn("DEEPSEEK_API_KEY", respuesta)
        self.assertIn("comandos", respuesta)
        self.assertNotIn("http", respuesta)


class TestConfigIA(Base):
    def test_valores_por_defecto(self):
        ia = bot_elio.config_ia({})
        self.assertEqual(ia["url"], bot_elio.API_IA)
        self.assertEqual(ia["modelo"], "deepseek-chat")
        self.assertIsNone(ia["clave"])

    def test_url_y_modelo_por_entorno(self):
        ia = bot_elio.config_ia({"IA_URL": "https://ia.local/chat",
                                 "IA_MODELO": "modelo-local"})
        self.assertEqual(ia["url"], "https://ia.local/chat")
        self.assertEqual(ia["modelo"], "modelo-local")

    def test_env_fichero_configura_la_ia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / ".env"
            ruta.write_text("IA_URL=https://ia.local/chat\nIA_MODELO=modelo-local\n"
                            "IA_API_KEY=clave-nueva\nDEEPSEEK_API_KEY=clave-vieja\n",
                            encoding="utf-8")
            with patch.dict(os.environ, {"IA_URL": "", "IA_MODELO": "",
                                         "IA_API_KEY": "", "DEEPSEEK_API_KEY": ""}):
                ia = bot_elio.config_ia(bot_elio.leer_env(ruta))
        self.assertEqual(ia["url"], "https://ia.local/chat")
        self.assertEqual(ia["modelo"], "modelo-local")
        self.assertEqual(ia["clave"], "clave-nueva")

    def test_entorno_gana_al_fichero(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / ".env"
            ruta.write_text("IA_URL=https://ia.local/fichero\n", encoding="utf-8")
            with patch.dict(os.environ, {"IA_URL": "https://ia.local/entorno"}):
                ia = bot_elio.config_ia(bot_elio.leer_env(ruta))
        self.assertEqual(ia["url"], "https://ia.local/entorno")

    def test_clave_respalda_en_deepseek(self):
        self.assertEqual(bot_elio.config_ia({"DEEPSEEK_API_KEY": "vieja"})["clave"],
                         "vieja")
        self.assertEqual(
            bot_elio.config_ia({"IA_API_KEY": "nueva",
                                "DEEPSEEK_API_KEY": "vieja"})["clave"], "nueva")

    def test_responder_api_usa_url_y_modelo(self):
        cliente = ClienteIA()
        bot_elio.responder_api("¿cómo va?", self.contexto, clave="clave-falsa",
                               cliente=cliente, url="https://ia.local/chat",
                               modelo="modelo-local")
        llamada = cliente.llamadas[0]
        self.assertEqual(llamada["url"], "https://ia.local/chat")
        self.assertEqual(llamada["cuerpo"]["model"], "modelo-local")

    def test_atender_pasa_la_configuracion_de_ia(self):
        estado = bot_elio.estado_vacio(self.contexto)
        actualizacion = {"update_id": 1,
                         "message": {"chat": {"id": 42}, "text": "¿va a llover?"}}
        capturado = {}

        def falso(pregunta, contexto, clave=None, cliente=None, timeout=30,
                  url=None, modelo=None):
            capturado.update({"clave": clave, "url": url, "modelo": modelo})
            return "No tengo ese dato."

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            with patch.object(bot_elio, "ESTADO", ruta), \
                    patch.object(bot_elio, "responder_api", falso):
                bot_elio.atender(actualizacion, estado, self.contexto, TOKEN_FALSO,
                                 clave="clave-falsa", cliente=ClienteTelegram(),
                                 ia={"url": "https://ia.local/chat",
                                     "modelo": "modelo-local"})
        self.assertEqual(capturado, {"clave": "clave-falsa",
                                     "url": "https://ia.local/chat",
                                     "modelo": "modelo-local"})


class TestToken(Base):
    def test_token_no_aparece_en_las_respuestas(self):
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": TOKEN_FALSO}):
            entorno = bot_elio.leer_env()
            self.assertEqual(entorno["TELEGRAM_TOKEN"], TOKEN_FALSO)
            salidas = [
                self.interpretar("/estado")["respuesta"],
                self.interpretar("/ayuda")["respuesta"],
                self.interpretar("/parcelas")["respuesta"],
                self.interpretar("/clima")["respuesta"],
                bot_elio.responder_api("¿va a llover?", self.contexto, clave=None),
            ]
        for salida in salidas:
            self.assertNotIn("secreto-de-prueba", salida)
            self.assertNotIn("123456", salida)

    def test_env_prioriza_variables_de_entorno(self):
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": TOKEN_FALSO}):
            self.assertEqual(bot_elio.leer_env()["TELEGRAM_TOKEN"], TOKEN_FALSO)

    def test_clave_de_ia_no_aparece_en_las_salidas(self):
        with patch.dict(os.environ, {"IA_API_KEY": "clave-ia-secreta"}):
            salidas = [
                bot_elio.responder_api("¿va a llover?", self.contexto, clave=None),
                bot_elio.responder_api("¿va a llover?", self.contexto,
                                       clave="clave-ia-secreta",
                                       cliente=ClienteIA(falla=True)),
            ]
        for salida in salidas:
            self.assertNotIn("clave-ia-secreta", salida)


class TestProceso(Base):
    def test_atender_escribe_el_estado(self):
        estado = bot_elio.estado_vacio(self.contexto)
        cliente = ClienteTelegram()
        actualizacion = {"update_id": 7,
                         "message": {"chat": {"id": 42}, "text": "/techo on"}}
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            with patch.object(bot_elio, "ESTADO", ruta):
                bot_elio.atender(actualizacion, estado, self.contexto,
                                 TOKEN_FALSO, clave=None, cliente=cliente)
            leido = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(list(pathlib.Path(carpeta).glob("*.json")), [ruta])
        self.assertIs(leido["parcelas"]["la-esperanza"]["techo"], True)
        self.assertEqual(leido["modo"], "comandos")
        self.assertEqual(leido["historial"][-1]["texto"], "/techo on")
        self.assertEqual(cliente.envios[0]["datos"]["chat_id"], 42)

    def test_simular_escribe_solo_el_estado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            with patch.object(bot_elio, "ESTADO", ruta), contextlib.redirect_stdout(io.StringIO()):
                bot_elio.simular("/techo on")
            archivos = sorted(p.name for p in pathlib.Path(carpeta).iterdir())
            self.assertEqual(archivos, ["estado_finca.json"])
            leido = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertIs(leido["parcelas"]["la-esperanza"]["techo"], True)
        self.assertTrue(leido["actualizado"])
        self.assertEqual(leido["origen"], "telegram")

    def test_latido_mantiene_fresco_el_estado(self):
        cliente = ClienteCorta()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            with patch.object(bot_elio, "ESTADO", ruta), \
                    patch.object(bot_elio, "LATIDO_SEGUNDOS", 0), \
                    contextlib.redirect_stdout(io.StringIO()):
                codigo = bot_elio.arrancar(
                    {"TELEGRAM_TOKEN": TOKEN_FALSO}, cliente)
            leido = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(codigo, 0)
        self.assertIn("actualizado", leido)
        self.assertEqual(leido["origen"], "telegram")

    def test_simular_no_escribe_si_es_ia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = pathlib.Path(carpeta) / "estado_finca.json"
            with patch.object(bot_elio, "ESTADO", ruta), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bot_elio.simular("¿va a llover?"), 1)
            self.assertFalse(ruta.exists())


if __name__ == "__main__":
    unittest.main()
