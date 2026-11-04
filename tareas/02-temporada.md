# Tarea 2 · Seguimiento de la temporada (Open-Meteo)

**Entrega:** `tools/reciente.py` (lógica pura) + `actualizar_reciente.py`
(red y escritura) + `datos/reciente.json`, `datos/reciente.js` y
`datos/climatologia_era5.json`. **≈5 h.** Depende de la tarea 1 solo para las
fincas (`datos/fincas.json`).

**Rama:** `tarea/2-temporada` · **Commit:** `feat(temporada): últimos 30 días, anomalías y caché`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/2-temporada
# ... trabajas ...
git add <los archivos de "Permitido tocar">
git commit -m "feat(temporada): últimos 30 días, anomalías y caché"
git push -u origin tarea/2-temporada
# luego abre el PR en GitHub: base main <- tarea/2-temporada
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/2-temporada`. Si ya empujaste a `main` por error, no fuerces:
avisa y se revierte.

## Permitido tocar

- `tools/reciente.py` (nuevo)
- `actualizar_reciente.py` (nuevo)
- `datos/reciente.json`, `datos/reciente.js`, `datos/climatologia_era5.json`
  (generados; se commitean)
- `tests/test_reciente.py` (nuevo)
- `tests/fixtures/openmeteo_constanza.json`, `openmeteo_azua.json`,
  `openmeteo_sfm.json` (respuestas reales recortadas)
- `tests/fixtures/reciente_ejemplo.json` (**entrégalo el día 1**, para la tarea 3)

## Prohibido

`web/`, `datos/fincas.json`, `tools/power_cliente.py`, `tools/rotaciones.py`,
`tests/test_reciente_casos.py` (esa es la tarea 5).

## Regla que no se puede romper

La anomalía compara **el mismo tipo de fuente**: dato reciente de Open-Meteo
contra normal de **Open-Meteo/ERA5**. POWER no entra aquí. Restar una normal de
POWER (MERRA-2) a un dato de ERA5 mide la diferencia entre modelos, no el clima:
la validación del repo vio cocientes POWER/ERA5 de **0.36 a 4.78** en Constanza.
POWER se usa para la lente NASA de largo plazo (tendencias y motor de rotaciones),
no para esta anomalía.

## Fuentes (verificadas hoy)

**Reciente** (sin retraso, es la que se muestra):

```
GET https://api.open-meteo.com/v1/forecast
  latitude, longitude, timezone=America/Santo_Domingo
  daily=precipitation_sum,temperature_2m_max,temperature_2m_min
  hourly=soil_moisture_0_to_7cm
  past_days=45
  forecast_days=7
```

**Normal 1991–2020** (misma familia ERA5, con retraso de ~5 días: solo se usa
para climatología, no para el dato reciente):

```
GET https://archive-api.open-meteo.com/v1/archive
  latitude, longitude, timezone=America/Santo_Domingo
  daily=precipitation_sum
  start_date=1991-01-01, end_date=2020-12-31
```

Medido hoy: 10.958 días, ~2,4 s y ~210 KB por finca, sin nulos.

- Sin clave en ninguna de las dos. No es NASA: `fuente.no_nasa = true`.
- Unidades: léelas de `daily_units` / `hourly_units`; si `precipitation_sum` no
  es `mm` o `soil_moisture_0_to_7cm` no es `m³/m³`, añade aviso y no conviertas.
- `soil_moisture_0_to_7cm` viene **por hora**: media diaria (24 valores; si
  faltan horas, `null`). Es la capa **0–7 cm**, no la zona radicular.
- Pronóstico = fechas `> hoy`; histórico = `<= hoy`.

## Contrato

Salida exacta en [00-contratos.md](00-contratos.md#datosrecientjson) y
[`datos/climatologia_era5.json`](00-contratos.md#datosclimatologia_era5json).
Reglas que más se rompen:

- `serie_30d`: **30 entradas**, `fin = ayer`, `inicio = fin − 29`.
- `pronostico`: 7 entradas o `[]` + aviso.
- `actualizado` con offset de la zona de la finca.
- Falta de dato = `null` + frase en `avisos` (nunca `0`).
- `climatologia_era5.json`: totales **mensuales en mm** (`lluvia_mm`), 30 años.

## Funciones de `tools/reciente.py` (puras, sin red, sin I/O)

```python
def percentil(valores, q):                        # q en 0..1, None si no hay datos
def ventana(fin, dias=30):                        # (inicio, fin) con date
def construir_climatologia(diario, anio_ini, anio_fin):  # {"1991": {"lluvia_mm": [...12]}}
def normal_ventana(climatologia, inicio, fin):    # {"lluvia_mm": float|None}
def banda_por_anio(climatologia, inicio, fin):    # (p25, p75) | None
def anomalia_lluvia(acum, normal, banda):         # {"30d_mm","normal_mm","pct","banda","estado"}
def anomalia_temperatura(media, normal, banda):   # {"media","normal","delta","banda","estado"}
def anomalia_humedad(horas, fechas, ahora):       # {"valor","unidad","cambio_7d","banda":None,"nota"}
def construir_finca(finca, respuesta, climatologia, ahora):  # dict del contrato
def construir_reciente(fincas, respuestas, climatologias, ahora):  # {"version", ...}
def evaluar_frescura(actualizado, ahora):         # {"dias": int, "aviso": str|None}
def leer_cache(ruta):                             # dict | None
def escribir_atomico(ruta, objeto):               # .tmp + os.replace
```

- `normal_ventana` y `banda_por_anio` ponderan por días reales de cada mes
  (ventana que cruza de mes: 12 días de octubre + 18 de noviembre, por ejemplo).
  Va con `shortcut:` en el código: reparto proporcional a días.
- `evaluar_frescura`: `dias` entre `actualizado` y `ahora`; aviso
  `"datos de hace N días"` si `N > 3`; `{"dias": 0, "aviso": None}` si es hoy.

## `actualizar_reciente.py`

1. Lee `datos/fincas.json`. Si no existe, error claro y código 2.
2. Carga `datos/climatologia_era5.json` (si falta, lo genera con la red).
3. Por finca: pide Open-Meteo reciente (`urllib.request`, timeout 30 s,
   User-Agent `tierra/1.0`), construye el bloque y sigue. Si una finca falla,
   esa queda con `null`s y un aviso; **las demás se guardan**.
4. Si **todas** fallan: conserva `datos/reciente.json` como caché, imprime
   "sin conexión: se mantiene el dato de <fecha>" y sale con **código 1**.
5. Escribe `datos/reciente.json` y `datos/reciente.js` (mismo objeto) de forma
   atómica y en ese orden; luego imprime `actualizado`, fincas y avisos.
6. `--sin-red`: no llama a la red; usa `tests/fixtures/openmeteo_*.json` para
   ejercitar el pipeline y escribir. Sirve para probar en la feria.
7. `--recalcular-climatologia`: vuelve a bajar 1991–2020 y reescribe
   `datos/climatologia_era5.json` (tócalo solo si hace falta; son 3 peticiones).

Para que la tarea 5 pueda probar el fallo de red, el script debe exponer además:

```python
def actualizar(fincas, pedir, ahora, ruta_json, ruta_js, climatologia):
    """Construye y escribe. pedir(finca) devuelve la respuesta de Open-Meteo o lanza.

    Si pedir lanza para todas las fincas: no reescribe nada y devuelve
    {"sin_conexion": True, "actualizado": <fecha del cache>}.
    """
```

`main()` solo arma `pedir`, `ahora`, las rutas y la climatología, y llama a
`actualizar`.

## Tests (`tests/test_reciente.py`, sin red)

1. `percentil` con lista conocida.
2. `construir_climatologia` con 3 meses de diario sintético → totales correctos.
3. `normal_ventana` cruzando mes: pesos correctos (comprobación a mano).
4. `banda_por_anio` con climatología sintética de 30 años.
5. `estado` en los tres tramos y `pct` con normal 0.
6. `construir_finca` con respuesta completa y con `soil_moisture` todo `null`.
7. `evaluar_frescura` hoy / 2 días / 6 días.
8. `leer_cache` con JSON roto devuelve `None`.

## Criterios de aceptación

```bash
python3 -m unittest tests.test_reciente -v          # todo OK
python3 actualizar_reciente.py --sin-red            # escribe sin red, 3 fincas
python3 - <<'PY'
import json
c = json.load(open("datos/climatologia_era5.json"))
assert len(c["fincas"]) == 3
assert all(len(f["mensual"]) == 30 for f in c["fincas"])
assert all(len(v["lluvia_mm"]) == 12 for f in c["fincas"] for v in f["mensual"].values())
d = json.load(open("datos/reciente.json"))
assert len(d["fincas"]) == 3
for f in d["fincas"]:
    assert len(f["serie_30d"]) == 30
    assert len(f["pronostico"]) in (0, 7)
    assert f["humedad_superficial"]["banda"] is None
print("climatologia y reciente OK", d["actualizado"])
PY
```

## Trampas

- No uses `datetime.now()` dentro de las funciones puras: pasá `ahora`.
- Zona horaria: `zoneinfo.ZoneInfo(finca["zona_horaria"])`, nunca la de la máquina.
- Un día sin horas de humedad es `null`, no `0.0`.
- **No** calcules la normal con POWER aunque sea lo primero que encuentres.
- `pct` con `normal_mm == 0` → `null`, no división por cero.
- El archivo de 30 años tarda ~2,4 s por finca: no lo pidas en cada corrida si
  ya existe; solo con `--recalcular-climatologia`.

## Si te bloqueas

Issue `Tarea 2 · <duda>`. Si Open-Meteo cambia una unidad o un parámetro, **no
adivines**: campo `null`, aviso y aviso en el issue.
