# Tarea 2 · Seguimiento de la temporada (Open-Meteo)

**Entrega:** `tools/reciente.py` (lógica pura) + `actualizar_reciente.py`
(red y escritura) + `datos/reciente.json` y `datos/reciente.js`.
**≈4 h.** Depende de la tarea 1 (`datos/fincas.json`).

**Rama:** `tarea/2-temporada` · **Commit:** `feat(temporada): últimos 30 días, anomalías y caché`

## Permitido tocar

- `tools/reciente.py` (nuevo)
- `actualizar_reciente.py` (nuevo)
- `datos/reciente.json` y `datos/reciente.js` (generados; se commitean)
- `tests/test_reciente.py` (nuevo)
- `tests/fixtures/openmeteo_constanza.json`, `openmeteo_azua.json`,
  `openmeteo_sfm.json` (respuestas reales recortadas)
- `tests/fixtures/reciente_ejemplo.json` (**entrégalo el día 1**, para la tarea 3)

## Prohibido

`web/`, `datos/fincas.json`, `tools/power_cliente.py`, `tools/rotaciones.py`,
`tests/test_reciente_casos.py` (esa es la tarea 5).

## Fuente (verificada hoy)

```
GET https://api.open-meteo.com/v1/forecast
  latitude, longitude
  timezone=America/Santo_Domingo
  daily=precipitation_sum,temperature_2m_max,temperature_2m_min
  hourly=soil_moisture_0_to_7cm
  past_days=45
  forecast_days=7
```

- Sin clave. No es NASA: `fuente.no_nasa = true`.
- `past_days` trae el análisis reciente **sin el retraso de la API de archivo**
  (esa tiene ~5 días). No uses `archive-api` para "esta temporada".
- Unidades: léelas de `daily_units` / `hourly_units`; no las escribas a mano.
  Si `precipitation_sum` no es `mm` o `soil_moisture_0_to_7cm` no es `m³/m³`,
  añade un aviso y no conviertas a ciegas.
- `soil_moisture_0_to_7cm` viene **por hora**: agrega a media diaria (24 valores;
  si faltan horas, `null` para ese día).
- El pronóstico son las fechas `> hoy`; el histórico, `<= hoy`.

## Contrato

Salida exacta en [00-contratos.md](00-contratos.md#datosrecientjson).
Reglas que más se rompen:

- `serie_30d`: **30 entradas**, una por día, `fin = ayer`, `inicio = fin − 29`.
- `pronostico`: 7 entradas o `[]` + aviso.
- `actualizado` con offset de la zona de la finca.
- `humedad_raiz.banda` siempre `null`.
- Falta de dato = `null` + frase en `avisos` (nunca `0`).

## Funciones de `tools/reciente.py` (puras, sin red, sin I/O)

```python
def percentil(valores, q):                     # q en 0..1, None si no hay datos
def ventana(fin, dias=30):                     # (inicio, fin) con date
def normal_ventana(climatologia, inicio, fin): # {"lluvia_mm": float|None, "t2m": float|None}
def banda_por_anio(climatologia, inicio, fin): # {"lluvia_mm": (p25, p75)|None, "t2m": (...) |None}
def anomalia_lluvia(acum, normal, banda):      # {"30d_mm", "normal_mm", "pct", "banda", "estado"}
def anomalia_temperatura(media, normal, banda):# {"media", "normal", "delta", "banda", "estado"}
def anomalia_humedad(horas, fechas, ahora):    # {"valor", "unidad", "cambio_7d", "banda": None, "nota"}
def construir_finca(finca, respuesta, ahora):  # dict del contrato
def construir_reciente(fincas, respuestas, ahora):  # {"version", "actualizado", ...}
def evaluar_frescura(actualizado, ahora):      # {"dias": int, "aviso": str|None}
def leer_cache(ruta):                          # dict | None (JSON inválido -> None)
def escribir_atomico(ruta, objeto):            # .tmp + os.replace
```

- `normal_ventana` y `banda_por_anio` ponderan por días reales de cada mes
  (ventana que cruza de mes: 12 días de octubre + 18 de noviembre, por ejemplo).
- `evaluar_frescura`: `dias` = días de calendario entre `actualizado` y `ahora`;
  aviso `"datos de hace N días"` si `N > 3`; `{"dias": 0, "aviso": None}` si es hoy.

## `actualizar_reciente.py`

1. Lee `datos/fincas.json`. Si no existe, error claro y código 2.
2. Por finca: pide Open-Meteo (`urllib.request`, timeout 30 s, User-Agent
   `tierra/1.0`), construye el bloque y sigue. Si una finca falla, esa finca
   queda con `null`s y un aviso; **las demás se guardan**.
3. Si **todas** fallan: conserva `datos/reciente.json` como caché, imprime
   "sin conexión: se mantiene el dato de <fecha>" y sale con **código 1**.
4. Escribe `datos/reciente.json` y `datos/reciente.js` (mismo objeto) de forma
   atómica y en ese orden; luego imprime `actualizado`, fincas y avisos.
5. `--sin-red`: no llama a la red; usa `tests/fixtures/openmeteo_*.json` para
   ejercitar todo el pipeline y escribir. Sirve para probar en la feria.

Para que la tarea 5 pueda probar el fallo de red, el script debe exponer además:

```python
def actualizar(fincas, pedir, ahora, ruta_json, ruta_js):
    """Construye y escribe. pedir(finca) devuelve la respuesta de Open-Meteo o lanza.

    Si pedir lanza para todas las fincas: no reescribe nada y devuelve
    {"sin_conexion": True, "actualizado": <fecha del cache>}.
    """
```

`main()` solo arma `pedir`, `ahora` y las rutas, y llama a `actualizar`.

## Tests (`tests/test_reciente.py`, sin red)

1. `percentil` con lista conocida.
2. `normal_ventana` cruzando mes: pesos correctos (comprobación numérica a mano).
3. `banda_por_anio` con climatología sintética de 30 años.
4. `estado` en los tres tramos (por_debajo/normal/por_encima) y `pct` con normal 0.
5. `construir_finca` con respuesta completa y con `soil_moisture` todo `null`.
6. `evaluar_frescura` hoy / 2 días / 6 días.
7. `leer_cache` con JSON roto devuelve `None`.

## Criterios de aceptación

```bash
python3 -m unittest tests.test_reciente -v          # todo OK
python3 actualizar_reciente.py --sin-red            # escribe sin red, 3 fincas
python3 - <<'PY'
import json
d = json.load(open("datos/reciente.json"))
assert len(d["fincas"]) == 3
for f in d["fincas"]:
    assert len(f["serie_30d"]) == 30
    assert len(f["pronostico"]) in (0, 7)
    assert f["humedad_raiz"]["banda"] is None
print("reciente.json OK", d["actualizado"])
PY
```

## Trampas

- No uses `datetime.now()` dentro de las funciones puras: pasá `ahora` como
  parámetro (si no, los tests dependen del día).
- Zona horaria: `zoneinfo.ZoneInfo(finca["zona_horaria"])`; no uses la hora local
  de la máquina.
- Un día sin horas de humedad es `null`, no `0.0`.
- No inventes banda de humedad ni la compares con POWER: se dice "sin
  climatología comparable".
- `pct` con `normal_mm == 0` → `null`, no división por cero.

## Si te bloqueas

Issue `Tarea 2 · <duda>`. Si Open-Meteo cambia una unidad o un nombre de
parámetro, **no adivines**: deja el campo en `null`, añade un aviso y avisa en
el issue.
