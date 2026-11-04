# Tarea 1 · Climatología de las fincas piloto

**Entrega:** `generar_fincas.py` + `datos/fincas.json` con 3 fincas y 30 años de
climatología mensual de NASA POWER (1991–2020). **≈3 h.**

**Rama:** `tarea/1-datos` · **Commit:** `feat(datos): fincas piloto y climatología POWER`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/1-datos
# ... trabajas ...
git add <los archivos de "Permitido tocar">
git commit -m "feat(datos): fincas piloto y climatología POWER"
git push -u origin tarea/1-datos
# luego abre el PR en GitHub: base main <- tarea/1-datos
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/1-datos`. Si ya empujaste a `main` por error, no fuerces:
avisa y se revierte.


## Permitido tocar

- `generar_fincas.py` (nuevo)
- `datos/fincas.json` (nuevo, generado; se commitea)
- `tools/power_cliente.py` — **solo añadir** dos funciones al final; no tocar
  `descargar_celda`, `ErrorPower`, `_f` ni las constantes.
- `tests/test_fincas.py` (nuevo)
- `tests/fixtures/power_mensual.json` (nuevo, respuesta real recortada)

## Prohibido

`web/`, `tools/tendencia.py`, `tools/malla_global.py`, `tools/eventos.py`,
`tests/test_power_cliente.py`, `README.md`, `AGENTS.md`, `docs/`, `datos/reciente.json`.

## Contrato

Salida exacta en [00-contratos.md](00-contratos.md#datosfincasjson). Resumen:

- 3 fincas: `constanza` (18.91, −70.74), `azua` (18.45, −70.73),
  `san_francisco_de_macoris` (19.30, −70.25). Coordenadas ya usadas en
  `validar_power.py`; no inventar otras.
- `zona_horaria`: `America/Santo_Domingo` para las tres.
- `climatologia.mensual`: un objeto por año 1991–2020 (`{"1991": {...}, ... "2020": {...}}`),
  cada uno con `lluvia_mm_dia` y `t2m`, 12 números cada uno.
- `lluvia_mm_dia` es **tasa diaria** (mm/día), no acumulado mensual.

## Funciones a añadir en `tools/power_cliente.py`

```python
def parsear_mensual(datos, variables, anio_ini, anio_fin):
    """Convierte la respuesta JSON de POWER en {variable: {anio: {mes: valor|None}}}.

    Puro: no toca la red. Claves de POWER: "<AAAA><MM>" (MM de 01 a 12).
    Descarta "AAAA13" (anual). Relleno -999 -> None.
    """

def descargar_mensual(lat, lon, variables, anio_ini, anio_fin):
    """Pide POWER mensual y devuelve parsear_mensual(...). Mismos errores que
    ErrorPower y misma cabecera de parámetros que descargar_celda
    (parameters, community=AG, latitude, longitude, start, end, format=JSON).
    """
```

Nota: la API mensual **solo acepta años** en `start`/`end` (no fechas).
`descargar_celda` no sirve para esto porque devuelve solo la clave anual `AAAA13`.

## Pasos

1. `datos/` no existe: créala con `mkdir -p datos`.
2. Implementa `parsear_mensual` y `descargar_mensual` como arriba.
3. Guarda una respuesta real recortada (una finca, 1991) en
   `tests/fixtures/power_mensual.json` para probar sin red.
4. Escribe `generar_fincas.py`:
   - constante `FINCAS` con los 3 diccionarios base (sin climatología);
   - `construir_finca(finca, mensual) -> dict` (puro, testeable);
   - `main()` con `--verificar` (imprime nombre, lluvia media anual en mm y T
     media anual por finca, sin escribir), `--salida` (por defecto
     `datos/fincas.json`) y `--desde/--hasta` (1991/2020);
   - escribe con `json.dump(..., ensure_ascii=False, indent=1)` + `os.replace`
     (atómico) y termina con `print` de resumen.
   - Si una finca falla, aborta sin escribir (no dejes un JSON a medias).
5. `tests/test_fincas.py` (unittest, sin red):
   - `test_parsear_mensual` con el fixture: 12 meses, `None` en el relleno, sin `AAAA13`;
   - `test_construir_finca`: 30 años, 12 valores por año;
   - `test_json_publicado`: si existe `datos/fincas.json`, valida 3 fincas,
     `periodo == [1991, 2020]`, sin `NaN` (`math.isnan` sobre los floats),
     y que `sum(12)` valores por año sea 30.
6. Genera el JSON real una vez (necesita red) y **commitéalo**.

## Criterios de aceptación

```bash
python3 generar_fincas.py --verificar          # 3 líneas, sin escribir
python3 -m unittest tests.test_fincas -v       # todo OK
python3 - <<'PY'
import json, math
d = json.load(open("datos/fincas.json"))
assert len(d["fincas"]) == 3
for f in d["fincas"]:
    m = f["climatologia"]["mensual"]
    assert len(m) == 30 and all(len(v["lluvia_mm_dia"]) == 12 for v in m.values())
    assert not any(math.isnan(x) for v in m.values() for x in v["lluvia_mm_dia"] if x is not None)
print("fincas.json OK")
PY
ls -lh datos/fincas.json                        # menos de 400 KB
```

Pega esa salida en el PR.

## Trampas

- POWER devuelve `-999` para hueco: conviértelo a `null`, nunca a `0`.
- No redondees la lluvia a 0 decimales: se pierden los meses secos.
- La petición mensual con `start=1991-01` falla; son años pelados.
- No uses `datetime` para calcular mes/año: las claves son texto `AAAA` + `MM`.
- Si la red falla, no reescribas el JSON existente.

## Si te bloqueas

Abre un issue `Tarea 1 · <duda>` y no inventes coordenadas, periodos ni
variables. Si POWER tarda, no subas el timeout por encima de 90 s.
