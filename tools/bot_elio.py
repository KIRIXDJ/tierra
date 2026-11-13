"""Bot real de Telegram de TIERRA (Elio): dos modos en un solo proceso.

- **Modo comandos**: /estado, /parcelas, /clima, /rotaciones, /riego, /techo,
  /ventilar, /foto y /ayuda. Cada cambio de actuador reescribe
  ``datos/estado_finca.json`` (escritura atómica) para que la app web lo lea.
- **Modo API**: texto libre (o ``/ia <pregunta>``) va a DeepSeek con el contexto
  estructurado de ``datos/*.json`` y el contrato de Elio (breve, solo con
  contexto, cita fuente, "No tengo ese dato.", nada inventado).

El token vive en ``.env`` (gitignored) y **nunca** se imprime. Sin token no hay
bot; sin DEEPSEEK_API_KEY el bot sigue en modo comandos.

Uso:
    python3 tools/bot_elio.py                     # long polling real
    python3 tools/bot_elio.py --autoprueba       # chequeo sin red
    python3 tools/bot_elio.py --ping             # getMe, sin imprimir el token
    python3 tools/bot_elio.py --simular "/techo on"

Lo que es real y lo que no: los datos de clima son reales (NASA POWER,
ERA5/Open-Meteo, ISRIC SoilGrids) y el mapa es satélite real de Esri (no NASA);
las parcelas, los sensores y los actuadores son simulación de demo.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import pathlib
import time
import unicodedata

import requests

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
ESTADO = DATOS / "estado_finca.json"
OFFSET = RAIZ / ".offset_bot.json"
ENV = RAIZ / ".env"

API_TELEGRAM = "https://api.telegram.org/bot{token}/{metodo}"
API_IA = "https://api.deepseek.com/chat/completions"
MODELO_IA = "deepseek-chat"
MAX_HISTORIAL = 20
MAX_TEXTO_HISTORIAL = 240
MAX_RESPUESTA_HISTORIAL = 600
REPOSO_INICIAL = 2   # segundos de espera tras un fallo de red, se duplica hasta el máximo
REPOSO_MAXIMO = 60
LATIDO_SEGUNDOS = 60  # la app da el bot por conectado si "actualizado" es reciente (<3 min)

ACTUADORES = ("riego", "techo", "ventilacion")
TITULOS = {"riego": "Riego", "techo": "Techo", "ventilacion": "Ventilación"}
VALORES = {
    "on": True, "encender": True, "encendido": True, "abrir": True, "abre": True,
    "si": True, "sí": True, "1": True,
    "off": False, "apagar": False, "apagado": False, "cerrar": False, "cierra": False,
    "no": False, "0": False,
    "auto": "auto",
}

FUENTES = {
    "clima": "ERA5/Open-Meteo (modelo, no NASA)",
    "fincas": "NASA POWER (reanálisis MERRA-2)",
    "suelo": "ISRIC SoilGrids 2.0",
    "mapa": "Esri World Imagery (no NASA)",
}

PROMPT_SISTEMA = (
    "Eres Elio, el asistente agrícola de TIERRA (NASA Space Apps 2026). "
    "Reglas: respondes SOLO con el contexto JSON que se te adjunta (parcelas, "
    "clima reciente ERA5/Open-Meteo, fincas NASA POWER, rotaciones y suelo ISRIC "
    "SoilGrids). Español, máximo 3 frases, sin markdown. Cita la fuente de cada "
    "cifra: POWER, ERA5/Open-Meteo, ISRIC SoilGrids o Esri. Si el dato no está "
    "en el contexto, responde exactamente: \"No tengo ese dato.\" "
    "Jamás inventes cifras, fechas ni URLs."
)

AYUDA = "\n".join([
    "Soy Elio, el bot de TIERRA. Comandos:",
    "/estado [parcela] — actuadores de una parcela",
    "/parcelas — lista de parcelas",
    "/clima [parcela] — últimos 30 días (ERA5/Open-Meteo)",
    "/rotaciones [parcela] — estrategias y meses secos",
    "/riego on|off|auto [parcela]",
    "/techo on|off|auto [parcela]",
    "/ventilar on|off [parcela]",
    "/foto [parcela] — recorte satelital real (Esri)",
    "/ayuda — esta lista",
    "Sin argumento uso la primera parcela; \"todas\" aplica a todas.",
    "También puedes escribirme una pregunta y la contesto con los datos del sistema.",
])


# ---------------------------------------------------------------- utilidades

def _ahora():
    """ISO 8601 con la zona local (la hora que ve el agricultor)."""
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def _leer_json(ruta):
    try:
        return json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _normalizar(texto):
    """Minúsculas y sin tildes: 'La Esperanza' y 'la esperanza' son lo mismo."""
    limpio = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
    return "".join(letra for letra in limpio if not unicodedata.combining(letra))


def _fmt(valor, sufijo=""):
    if valor is None:
        return "sin dato"
    if isinstance(valor, (int, float)):
        return f"{valor:g}{sufijo}"
    return f"{valor}{sufijo}"


def leer_env(ruta=None):
    """Lee .env con parser propio; las variables de entorno tienen prioridad."""
    ruta = pathlib.Path(ruta or ENV)
    valores = {}
    try:
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        pass
    for clave in ("TELEGRAM_TOKEN", "DEEPSEEK_API_KEY"):
        if os.environ.get(clave):
            valores[clave] = os.environ[clave]
    return valores


# ---------------------------------------------------------------- contexto

def cargar_datos(carpeta=None):
    """Carga los JSON de datos/. Un archivo que falle queda como {} (tolerante)."""
    carpeta = pathlib.Path(carpeta or DATOS)
    nombres = ("parcelas", "reciente", "fincas", "rotaciones", "suelo")
    return {nombre: _leer_json(carpeta / f"{nombre}.json") for nombre in nombres}


def _parcela_resumen(parcela):
    return {
        "id": parcela.get("id"),
        "nombre": parcela.get("nombre"),
        "cultivo": parcela.get("cultivo"),
        "area_ha": parcela.get("area_ha"),
        "humedad_inicial": parcela.get("humedad_inicial"),
        "temperatura": parcela.get("temperatura"),
        "sensores": [s.get("id") for s in parcela.get("sensores") or []],
        "camara": parcela.get("camara"),
        "poligono_m": parcela.get("poligono_m"),
    }


def _clima_reciente(reciente):
    fuente = reciente.get("fuente") or {}
    bloques = []
    for finca in reciente.get("fincas") or []:
        lluvia = finca.get("lluvia") or {}
        temperatura = finca.get("temperatura") or {}
        humedad = finca.get("humedad_superficial") or {}
        bloques.append({
            "id": finca.get("id"),
            "nombre": finca.get("nombre"),
            "lluvia_30d_mm": lluvia.get("30d_mm"),
            "lluvia_normal_mm": lluvia.get("normal_mm"),
            "lluvia_pct": lluvia.get("pct"),
            "lluvia_estado": lluvia.get("estado"),
            "t2m_media": temperatura.get("media"),
            "t2m_normal": temperatura.get("normal"),
            "t2m_delta": temperatura.get("delta"),
            "t2m_estado": temperatura.get("estado"),
            "humedad_superficial": {
                "valor": humedad.get("valor"),
                "unidad": humedad.get("unidad"),
                "nota": humedad.get("nota"),
            },
        })
    return {
        "fuente": fuente.get("nombre"),
        "no_nasa": fuente.get("no_nasa"),
        "nota": fuente.get("nota"),
        "ventana": reciente.get("ventana"),
        "fincas": bloques,
    }


def _fincas_power(fincas):
    salida = []
    for finca in fincas.get("fincas") or []:
        climatologia = finca.get("climatologia") or {}
        mensual = climatologia.get("mensual") or {}
        lluvia = [v for mes in mensual.values()
                  for v in mes.get("lluvia_mm_dia") or [] if v is not None]
        t2m = [v for mes in mensual.values()
               for v in mes.get("t2m") or [] if v is not None]
        salida.append({
            "id": finca.get("id"),
            "nombre": finca.get("nombre"),
            "pais": finca.get("pais"),
            "lat": finca.get("lat"),
            "lon": finca.get("lon"),
            "zona_horaria": finca.get("zona_horaria"),
            "cultivo_actual": finca.get("cultivo_actual"),
            "periodo": climatologia.get("periodo"),
            "clima_fuente": climatologia.get("fuente"),
            "lluvia_media_mm_dia": round(sum(lluvia) / len(lluvia), 2) if lluvia else None,
            "t2m_media_c": round(sum(t2m) / len(t2m), 2) if t2m else None,
        })
    return salida


def _rotaciones(rotaciones):
    salida = []
    campos = ("id", "titulo", "cultivos", "demanda_agua", "meses_criticos",
              "indice", "provisional", "datos_faltantes")
    for finca in rotaciones.get("fincas") or []:
        salida.append({
            "finca": finca.get("id"),
            "meses_secos": finca.get("meses_secos"),
            "estrategias": [{campo: e.get(campo) for campo in campos}
                            for e in finca.get("estrategias") or []],
        })
    return {
        "fuente_clima": rotaciones.get("fuente_clima"),
        "fuente_suelo": rotaciones.get("fuente_suelo"),
        "fincas": salida,
    }


def _suelo(suelo):
    campos = ("id", "arcilla_pct", "arena_pct", "carbono_organico_g_kg", "ph", "textura")
    return {
        "fuente": suelo.get("fuente"),
        "profundidad": suelo.get("profundidad"),
        "avisos": suelo.get("avisos"),
        "fincas": [{campo: f.get(campo) for campo in campos}
                   for f in suelo.get("fincas") or []],
    }


def construir_contexto(datos):
    """Puro: resume datos/*.json en lo que ven la IA y los comandos. Sin URLs."""
    datos = datos or {}
    parcelas = datos.get("parcelas") or {}
    mapa = parcelas.get("mapa") or {}
    return {
        "finca": parcelas.get("finca"),
        "finca_nombre": parcelas.get("finca_nombre"),
        "nota": parcelas.get("nota"),
        "parcelas": [_parcela_resumen(p) for p in parcelas.get("parcelas") or []],
        "mapa": {
            "archivo": mapa.get("archivo"),
            "fuente": mapa.get("fuente"),
            "metros_por_pixel": mapa.get("metros_por_pixel"),
            "ancho_px": mapa.get("ancho_px"),
            "alto_px": mapa.get("alto_px"),
        },
        "clima_reciente": _clima_reciente(datos.get("reciente") or {}),
        "fincas_power": _fincas_power(datos.get("fincas") or {}),
        "rotaciones": _rotaciones(datos.get("rotaciones") or {}),
        "suelo": _suelo(datos.get("suelo") or {}),
        "fuentes": dict(FUENTES),
    }


# ---------------------------------------------------------------- estado

def estado_vacio(contexto):
    """Estado inicial del contrato: todas las parcelas con los actuadores apagados."""
    parcelas = {}
    for parcela in (contexto or {}).get("parcelas") or []:
        if parcela.get("id"):
            parcelas[parcela["id"]] = {actuador: False for actuador in ACTUADORES}
    return {
        "version": 1,
        "origen": "telegram",
        "actualizado": _ahora(),
        "modo": "comandos",
        "parcelas": parcelas,
        "ultimo": {},
        "historial": [],
    }


def cargar_estado(contexto, ruta=None):
    """Lee datos/estado_finca.json si existe; si falta o está roto, estado vacío."""
    ruta = pathlib.Path(ruta or ESTADO)
    estado = estado_vacio(contexto)
    guardado = _leer_json(ruta)
    if not isinstance(guardado, dict):
        return estado
    for clave in ("version", "origen", "actualizado", "modo"):
        if clave in guardado:
            estado[clave] = guardado[clave]
    if isinstance(guardado.get("ultimo"), dict):
        estado["ultimo"] = guardado["ultimo"]
    if isinstance(guardado.get("historial"), list):
        estado["historial"] = guardado["historial"]
    for pid, valores in (guardado.get("parcelas") or {}).items():
        actual = estado["parcelas"].setdefault(
            pid, {actuador: False for actuador in ACTUADORES})
        if isinstance(valores, dict):
            for actuador in ACTUADORES:
                if isinstance(valores.get(actuador), bool):
                    actual[actuador] = valores[actuador]
    return estado


def guardar_estado(estado, ruta=None):
    """Escritura atómica (tmp + rename): la app nunca lee un JSON a medias."""
    ruta = pathlib.Path(ruta or ESTADO)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def aplicar_cambios(estado, cambios):
    """Aplica {id_parcela: {actuador: bool}} al estado (muta y devuelve)."""
    for pid, valores in (cambios or {}).items():
        actual = estado.setdefault("parcelas", {}).setdefault(
            pid, {actuador: False for actuador in ACTUADORES})
        for actuador, valor in (valores or {}).items():
            if actuador in ACTUADORES:
                actual[actuador] = bool(valor)
    return estado


def registrar(estado, texto, respuesta, modo):
    """Anota el último intercambio y recorta el historial a MAX_HISTORIAL."""
    entrada = {
        "texto": (texto or "")[:MAX_TEXTO_HISTORIAL],
        "respuesta": (respuesta or "")[:MAX_RESPUESTA_HISTORIAL],
        "ts": _ahora(),
    }
    estado["version"] = 1
    estado["origen"] = "telegram"
    estado["modo"] = modo
    estado["actualizado"] = entrada["ts"]
    estado["ultimo"] = entrada
    historial = list(estado.get("historial") or [])
    historial.append(entrada)
    estado["historial"] = historial[-MAX_HISTORIAL:]
    return estado


# ---------------------------------------------------------------- comandos

def _orden(respuesta=None, cambios=None, foto=None, api=None):
    return {"respuesta": respuesta, "cambios": cambios or {}, "foto": foto, "api": api}


def _resolver(argumento, contexto):
    """Parcelas del mensaje: sin argumento la primera, 'todas' todas, si no []."""
    parcelas = contexto.get("parcelas") or []
    buscado = _normalizar(argumento)
    if not buscado:
        return parcelas[:1]
    if buscado in ("todas", "todo", "all", "*"):
        return parcelas
    for parcela in parcelas:
        if buscado in (_normalizar(parcela.get("id")), _normalizar(parcela.get("nombre"))):
            return [parcela]
    return []


def _no_conozco(argumento):
    return (f"No conozco la parcela \"{str(argumento).strip()}\". "
            "Escribe /parcelas para ver las disponibles.")


def _texto_parcelas(contexto):
    parcelas = contexto.get("parcelas") or []
    if not parcelas:
        return "No tengo los datos de parcelas."
    finca = contexto.get("finca_nombre") or contexto.get("finca") or "la finca"
    lineas = [f"Parcelas de {finca}:"]
    for parcela in parcelas:
        lineas.append(f"· {parcela.get('id')} — {parcela.get('nombre')} · "
                      f"{parcela.get('cultivo')} · {_fmt(parcela.get('area_ha'))} ha")
    return "\n".join(lineas)


def _texto_estado(estado, parcelas):
    bloques = []
    for parcela in parcelas:
        actual = (estado.get("parcelas") or {}).get(parcela.get("id")) or {}
        bloques.append(
            f"{parcela.get('nombre')} ({parcela.get('cultivo')}, "
            f"{_fmt(parcela.get('area_ha'))} ha)\n"
            f"Riego {'encendido' if actual.get('riego') else 'apagado'} · "
            f"techo {'cerrado' if actual.get('techo') else 'abierto'} · "
            f"ventilación {'abierta' if actual.get('ventilacion') else 'cerrada'}\n"
            f"Humedad {_fmt(parcela.get('humedad_inicial'), ' %')} · "
            f"{_fmt(parcela.get('temperatura'), ' °C')} (sensor simulado)")
    return "\n\n".join(bloques)


def _texto_clima(contexto):
    finca = contexto.get("finca")
    bloque = next((b for b in (contexto.get("clima_reciente") or {}).get("fincas") or []
                   if b.get("id") == finca), None)
    if not bloque:
        return "No tengo ese dato."
    humedad = bloque.get("humedad_superficial") or {}
    return (
        f"Clima de {bloque.get('nombre')} · últimos 30 días "
        "(ERA5/Open-Meteo, modelo · no NASA):\n"
        f"Lluvia {_fmt(bloque.get('lluvia_30d_mm'), ' mm')} "
        f"(normal {_fmt(bloque.get('lluvia_normal_mm'), ' mm')}, "
        f"{_fmt(bloque.get('lluvia_pct'), ' %')}) → {bloque.get('lluvia_estado') or 'sin estado'}\n"
        f"Temperatura media {_fmt(bloque.get('t2m_media'), ' °C')} "
        f"(normal {_fmt(bloque.get('t2m_normal'), ' °C')}, "
        f"{_fmt(bloque.get('t2m_delta'), ' °C')}) → {bloque.get('t2m_estado') or 'sin estado'}\n"
        f"Humedad superficial {_fmt(humedad.get('valor'))} {humedad.get('unidad') or ''}\n"
        "Fuente: ERA5/Open-Meteo, modelo; no es un sensor de la parcela."
    )


def _texto_rotaciones(contexto):
    finca = contexto.get("finca")
    bloque = next((b for b in (contexto.get("rotaciones") or {}).get("fincas") or []
                   if b.get("finca") == finca), None)
    if not bloque:
        return "No tengo ese dato."
    nombres = {f.get("id"): f.get("nombre") for f in contexto.get("fincas_power") or []}
    secos = ", ".join(str(mes) for mes in bloque.get("meses_secos") or []) or "sin dato"
    lineas = [f"Rotaciones en {nombres.get(finca) or finca} "
              f"(orientativo, provisional). Meses secos: {secos}."]
    for estrategia in bloque.get("estrategias") or []:
        cultivos = ", ".join(estrategia.get("cultivos") or []) or "sin cultivos"
        lineas.append(f"{estrategia.get('titulo')}: índice "
                      f"{estrategia.get('indice')} · {cultivos}")
    lineas.append("Clima: NASA POWER · suelo: ISRIC SoilGrids. "
                  "No es recomendación agronómica.")
    return "\n".join(lineas)


def _pie_foto(parcela):
    return (f"{parcela.get('nombre')} · {parcela.get('cultivo')} · "
            f"{_fmt(parcela.get('area_ha'))} ha\n"
            "Imagen satelital real de Esri World Imagery (no NASA). "
            "El polígono y los sensores son simulados.")


def _actuadores(comando, argumentos, contexto):
    """Arma los cambios de /riego, /techo o /ventilar; no toca el estado."""
    actuador = {"riego": "riego", "techo": "techo", "ventilar": "ventilacion"}[comando]
    partes = argumentos.split()
    valor = partes[0].lower() if partes else ""
    resto = " ".join(partes[1:])
    if valor not in VALORES:
        return _orden(f"Usa /{comando} on|off" +
                      ("|auto" if actuador != "ventilacion" else "") +
                      " [parcela].")
    if valor == "auto" and actuador == "ventilacion":
        return _orden("La ventilación solo acepta on u off.")
    parcelas = _resolver(resto, contexto)
    if not parcelas:
        return _orden(_no_conozco(resto))
    nuevo = False if valor == "auto" else VALORES[valor]
    cambios = {parcela["id"]: {actuador: nuevo} for parcela in parcelas}
    nombres = ", ".join(parcela.get("nombre") or parcela.get("id") for parcela in parcelas)
    if valor == "auto":
        return _orden(f"{TITULOS[actuador]} en automático "
                      f"(override quitado) en {nombres}.", cambios)
    estados = {
        "riego": ("encendido", "apagado"),
        "techo": ("cerrado", "abierto"),
        "ventilacion": ("abierta", "cerrada"),
    }[actuador]
    return _orden(f"{TITULOS[actuador]} {estados[0] if nuevo else estados[1]} "
                  f"en {nombres}.", cambios)


def interpretar_comando(texto, estado, contexto):
    """Puro (sin red ni disco): traduce un mensaje en respuesta y cambios.

    Devuelve {"respuesta", "cambios", "foto", "api"}:
    - respuesta: texto a enviar (None si hay que contestar con la IA).
    - cambios: {id_parcela: {actuador: bool}} que el llamador aplica al estado.
    - foto: id de parcela cuyo recorte satelital hay que enviar.
    - api: pregunta para la IA (texto libre o /ia).
    """
    texto = (texto or "").strip()
    if not texto:
        return _orden(AYUDA)
    if not texto.startswith("/"):
        return _orden(api=texto)

    partes = texto.split()
    comando = partes[0].split("@")[0].lower()
    argumentos = " ".join(partes[1:]).strip()

    if comando in ("/ayuda", "/help", "/start"):
        return _orden(AYUDA)
    if comando == "/parcelas":
        return _orden(_texto_parcelas(contexto))
    if comando in ("/estado", "/clima", "/rotaciones"):
        parcelas = _resolver(argumentos, contexto)
        if not parcelas:
            return _orden(_no_conozco(argumentos))
        if comando == "/estado":
            return _orden(_texto_estado(estado, parcelas))
        if comando == "/clima":
            return _orden(_texto_clima(contexto))
        return _orden(_texto_rotaciones(contexto))
    if comando in ("/riego", "/techo", "/ventilar"):
        return _actuadores(comando.lstrip("/"), argumentos, contexto)
    if comando == "/foto":
        parcelas = _resolver(argumentos, contexto)
        if not parcelas:
            return _orden(_no_conozco(argumentos))
        return _orden(_pie_foto(parcelas[0]), foto=parcelas[0]["id"])
    if comando == "/ia":
        return _orden(api=argumentos or "¿Cómo va la finca hoy?")
    return _orden("No entiendo ese comando. Escribe /ayuda para ver la lista.")


# ---------------------------------------------------------------- IA

def responder_api(pregunta, contexto, clave=None, cliente=None, timeout=30):
    """Pregunta libre a DeepSeek con el contrato de Elio. Nunca lanza."""
    if not clave:
        return ("No tengo configurada la clave de la IA (DEEPSEEK_API_KEY); "
                "sigo funcionando con comandos. Prueba /ayuda.")
    cuerpo = {
        "model": MODELO_IA,
        "temperature": 0.2,
        "max_tokens": 300,
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": "Contexto:\n" +
             json.dumps(contexto, ensure_ascii=False) +
             "\n\nPregunta: " + str(pregunta or "")},
        ],
    }
    try:
        respuesta = (cliente or requests).post(
            API_IA,
            headers={"Authorization": f"Bearer {clave}",
                     "Content-Type": "application/json"},
            json=cuerpo,
            timeout=timeout,
        )
        datos = respuesta.json()
        texto = (datos["choices"][0]["message"]["content"] or "").strip()
        return texto or "No tengo ese dato."
    except Exception:  # red, clave o formato: una frase humana y el bot sigue
        return ("No pude consultar la IA ahora mismo (red o clave); "
                "los comandos siguen funcionando.")


# ---------------------------------------------------------------- Telegram

def _url_telegram(metodo, token):
    return API_TELEGRAM.format(token=token, metodo=metodo)


def llamar_telegram(metodo, datos, token, cliente=None, timeout=35):
    """POST a la API del bot. Devuelve dict; nunca lanza ni imprime el token."""
    try:
        respuesta = (cliente or requests).post(
            _url_telegram(metodo, token), data=datos, timeout=timeout)
        cuerpo = respuesta.json()
        return cuerpo if isinstance(cuerpo, dict) else {"ok": False}
    except Exception:
        return {"ok": False}


def enviar_mensaje(chat_id, texto, token, cliente=None):
    """Manda texto plano (sin parse_mode, para que nada rompa el mensaje)."""
    cuerpo = llamar_telegram(
        "sendMessage", {"chat_id": chat_id, "text": (texto or "")[:4000]}, token, cliente)
    return bool(cuerpo.get("ok"))


def recortar_parcela(parcela, mapa, margen_m=15):
    """Recorte JPEG del mapa alrededor del polígono, en memoria (bytes) o None.

    El mapa está centrado en el origen de las parcelas: píxel = centro + metros/mpp.
    """
    try:
        from PIL import Image
    except ImportError:  # sin Pillow el bot sigue: /foto degrada a texto
        return None
    try:
        ruta = DATOS / (mapa.get("archivo") or "mapa_constanza.jpg")
        mpp = float(mapa["metros_por_pixel"])
        ancho = int(mapa["ancho_px"])
        alto = int(mapa["alto_px"])
        puntos = parcela.get("poligono_m") or []
        if len(puntos) < 3 or mpp <= 0:
            return None
        xs = [float(x) for x, _ in puntos]
        ys = [float(y) for _, y in puntos]
        caja = (
            max(0, round(ancho / 2 + (min(xs) - margen_m) / mpp)),
            max(0, round(alto / 2 + (min(ys) - margen_m) / mpp)),
            min(ancho, round(ancho / 2 + (max(xs) + margen_m) / mpp)),
            min(alto, round(alto / 2 + (max(ys) + margen_m) / mpp)),
        )
        if caja[2] - caja[0] < 8 or caja[3] - caja[1] < 8:
            return None
        recorte = Image.open(ruta).convert("RGB").crop(caja)
        recorte.thumbnail((900, 900))
        buffer = io.BytesIO()
        recorte.save(buffer, "JPEG", quality=85)
        return buffer.getvalue()
    except Exception:
        return None


def enviar_foto(chat_id, parcela, mapa, token, cliente=None):
    """sendPhoto con el recorte real de Esri; si algo falla, degrada a texto."""
    pie = _pie_foto(parcela)
    recorte = recortar_parcela(parcela, mapa)
    if not recorte:
        enviar_mensaje(
            chat_id,
            pie + "\n(No pude recortar la imagen; te queda el dato en texto.)",
            token, cliente)
        return False
    try:
        respuesta = (cliente or requests).post(
            _url_telegram("sendPhoto", token),
            data={"chat_id": chat_id, "caption": pie},
            files={"photo": ("parcela.jpg", recorte, "image/jpeg")},
            timeout=60,
        )
        return bool(respuesta.json().get("ok"))
    except Exception:
        enviar_mensaje(chat_id, pie + "\n(No pude enviar la imagen.)", token, cliente)
        return False


def leer_offset(ruta=None):
    """Offset de getUpdates persistido (0 si no existe o está roto)."""
    try:
        return int(_leer_json(ruta or OFFSET)["offset"])
    except (KeyError, TypeError, ValueError):
        return 0


def guardar_offset(offset, ruta=None):
    """Persiste el offset. Si no se puede, se repite algún update: no es grave."""
    ruta = pathlib.Path(ruta or OFFSET)
    try:
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_text(json.dumps({"offset": offset}) + "\n", encoding="utf-8")
        os.replace(temporal, ruta)
    except OSError:
        pass


# ---------------------------------------------------------------- proceso

def _parcela_por_id(pid, contexto):
    return next((p for p in contexto.get("parcelas") or [] if p.get("id") == pid), None)


def atender(actualizacion, estado, contexto, token, clave=None, cliente=None):
    """Procesa un update de Telegram: responde, anota y guarda el estado."""
    mensaje = actualizacion.get("message") or {}
    chat_id = (mensaje.get("chat") or {}).get("id")
    texto = (mensaje.get("text") or "").strip()
    if not chat_id or not texto:
        return estado

    orden = interpretar_comando(texto, estado, contexto)
    if orden.get("api") is not None:
        respuesta = responder_api(orden["api"], contexto, clave=clave)
        modo = "api"
        enviar_mensaje(chat_id, respuesta, token, cliente)
    else:
        aplicar_cambios(estado, orden.get("cambios"))
        respuesta = orden.get("respuesta") or ""
        modo = "comandos"
        if orden.get("foto"):
            enviar_foto(chat_id, _parcela_por_id(orden["foto"], contexto) or {},
                        contexto.get("mapa") or {}, token, cliente)
        else:
            enviar_mensaje(chat_id, respuesta, token, cliente)

    registrar(estado, texto, respuesta, modo)
    guardar_estado(estado)
    return estado


def arrancar(entorno=None, cliente=None):
    """Long polling con reintentos suaves: un corte de red no tumba el proceso."""
    entorno = entorno if entorno is not None else leer_env()
    token = entorno.get("TELEGRAM_TOKEN")
    if not token:
        print("Falta TELEGRAM_TOKEN en .env: copia el token del bot y vuelve a intentar.")
        return 1
    contexto = construir_contexto(cargar_datos())
    estado = cargar_estado(contexto)
    clave = entorno.get("DEEPSEEK_API_KEY")
    offset = leer_offset()
    espera = REPOSO_INICIAL
    ultimo_latido = time.monotonic()
    print(f"Elio escuchando ({'comandos + IA' if clave else 'solo comandos'}). "
          "Ctrl+C para parar.", flush=True)
    try:
        while True:
            respuesta = llamar_telegram(
                "getUpdates", {"offset": offset, "timeout": 25}, token, cliente)
            if not respuesta.get("ok"):
                print(f"Sin conexión con Telegram; reintento en {espera} s.", flush=True)
                time.sleep(espera)
                espera = min(espera * 2, REPOSO_MAXIMO)
                continue
            espera = REPOSO_INICIAL
            for actualizacion in respuesta.get("result") or []:
                offset = int(actualizacion.get("update_id", offset - 1)) + 1
                guardar_offset(offset)
                try:
                    atender(actualizacion, estado, contexto, token, clave, cliente)
                except Exception:  # un update raro no tumba el polling
                    print("No pude procesar un mensaje; sigo escuchando.", flush=True)
            # Latido: la app da el bot por conectado solo si "actualizado" es reciente.
            if time.monotonic() - ultimo_latido >= LATIDO_SEGUNDOS:
                estado["actualizado"] = _ahora()
                try:
                    guardar_estado(estado)
                except OSError:
                    pass  # si no se puede escribir, el polling sigue igual
                ultimo_latido = time.monotonic()
    except KeyboardInterrupt:
        print("\nBot detenido.", flush=True)
        return 0


# ---------------------------------------------------------------- flags

def autoprueba():
    """Chequeo sin red: datos, comandos, contexto, escritura atómica. Imprime OK."""
    import tempfile

    datos = cargar_datos()
    assert datos["parcelas"].get("parcelas"), "no se leyeron las parcelas"
    contexto = construir_contexto(datos)
    assert contexto["parcelas"] and contexto["clima_reciente"]["fincas"], \
        "el contexto quedó vacío"

    estado = estado_vacio(contexto)
    assert set(estado["parcelas"]) == {p["id"] for p in contexto["parcelas"]}, \
        "el estado inicial no cubre las parcelas"

    orden = interpretar_comando("/riego on la esperanza", estado, contexto)
    assert orden["cambios"] == {"la-esperanza": {"riego": True}}, \
        f"no interpretó /riego: {orden['cambios']!r}"
    aplicar_cambios(estado, orden["cambios"])
    assert estado["parcelas"]["la-esperanza"]["riego"] is True

    clima = interpretar_comando("/clima", estado, contexto)["respuesta"]
    assert "Open-Meteo" in clima and "http" not in clima, "el clima no cita fuente"

    assert "No tengo ese dato." in PROMPT_SISTEMA, "falta el contrato de la IA en el prompt"

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = pathlib.Path(carpeta) / "estado_finca.json"
        registrar(estado, "/riego on", "Riego encendido.", "comandos")
        guardar_estado(estado, ruta)
        leido = json.loads(ruta.read_text(encoding="utf-8"))
        assert leido["parcelas"]["la-esperanza"]["riego"] is True, \
            "la escritura atómica perdió el cambio"
        assert leido["actualizado"] and leido["historial"], "faltan marcas de tiempo"
        assert not list(pathlib.Path(carpeta).glob("*.tmp")), "quedó un temporal"
    print("OK")
    return 0


def ping(entorno=None):
    """getMe con el token de .env: imprime solo ok y el username, nunca el token."""
    entorno = entorno if entorno is not None else leer_env()
    token = entorno.get("TELEGRAM_TOKEN")
    if not token:
        print("Falta TELEGRAM_TOKEN en .env.")
        return 1
    respuesta = llamar_telegram("getMe", {}, token)
    if respuesta.get("ok"):
        print(f"ping ok · @{(respuesta.get('result') or {}).get('username')}")
        return 0
    print("ping falló: el token no responde o no hay red.")
    return 1


def simular(comando):
    """Aplica un comando y escribe datos/estado_finca.json sin red (prueba de app)."""
    contexto = construir_contexto(cargar_datos())
    estado = cargar_estado(contexto)
    orden = interpretar_comando(comando, estado, contexto)
    if orden.get("api") is not None:
        print("Para la IA hace falta red; prueba un comando (/ayuda).")
        return 1
    aplicar_cambios(estado, orden.get("cambios"))
    respuesta = orden.get("respuesta") or ""
    registrar(estado, comando, respuesta, "comandos")
    guardar_estado(estado)
    print(respuesta)
    print(f"estado escrito en {ESTADO}")
    return 0


def main(argv=None):
    analizador = argparse.ArgumentParser(description="Bot de Telegram de TIERRA (Elio)")
    grupo = analizador.add_mutually_exclusive_group()
    grupo.add_argument("--autoprueba", action="store_true",
                       help="comprueba datos, comandos y escritura atómica sin red")
    grupo.add_argument("--ping", action="store_true",
                       help="getMe con el token de .env (no imprime el token)")
    grupo.add_argument("--simular", metavar="COMANDO",
                       help='aplica un comando y escribe el estado (ej. "/techo on")')
    argumentos = analizador.parse_args(argv)
    if argumentos.autoprueba:
        return autoprueba()
    if argumentos.simular:
        return simular(argumentos.simular)
    entorno = leer_env()
    if argumentos.ping:
        return ping(entorno)
    return arrancar(entorno)


if __name__ == "__main__":
    raise SystemExit(main())
