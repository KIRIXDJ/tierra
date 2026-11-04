# Tarea 4 · Motor de rotaciones con clima POWER y contexto reciente

**Entrega:** `tools/rotaciones.py` (motor puro) + `generar_rotaciones.py`
(escribe `datos/rotaciones.json`) + `docs/rotaciones.md`. **≈5 h.**
Usa la climatología **POWER** de `datos/fincas.json` (lente NASA) y, si existe,
el bloque de temporada de `datos/reciente.json`.

**Rama:** `tarea/4-rotaciones` · **Commit:** `feat(rotaciones): motor con clima POWER y contexto de temporada`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/4-rotaciones
# ... trabajas ...
git add <los archivos de "Permitido tocar">
git commit -m "feat(rotaciones): motor con clima POWER y contexto de temporada"
git push -u origin tarea/4-rotaciones
# luego abre el PR en GitHub: base main <- tarea/4-rotaciones
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/4-rotaciones`. Si ya empujaste a `main` por error, no fuerces:
avisa y se revierte.

## Permitido tocar

- `tools/rotaciones.py` (nuevo)
- `generar_rotaciones.py` (nuevo)
- `datos/rotaciones.json` y `datos/rotaciones.js` (generados; se commitean)
- `tests/test_rotaciones.py` (nuevo)
- `docs/rotaciones.md` (nuevo: fuentes y fórmulas)

## Prohibido

`web/`, `datos/fincas.json`, `datos/reciente.json`, `tools/reciente.py`,
`tools/power_cliente.py`, `AGENTS.md`.

## Qué debe usar del clima (esto es lo que lo hace NASA)

Del bloque `climatologia.mensual` de **POWER** en `datos/fincas.json`:

1. **Meses secos de la finca**: los 3 meses con menor media de `lluvia_mm_dia`
   en 1991–2020. Se calcula, no se escribe a mano.
2. Cada estrategia declara `meses_criticos` (meses en que su cultivo necesita
   agua). Mientras no haya fuente (tarea 8), van marcados `provisional`.
3. **Componente `agua`** = `10 − 2.5 × |meses_criticos ∩ meses_secos|`, acotado a
   0..10. Es una heurística de diseño, no agronomía: dilo en el docstring y en
   `docs/rotaciones.md`.
4. **Componente `diversidad`** = `10 × (número de cultivos distintos / 3)`,
   acotado a 0..10. Es aritmética, no opinión.
5. Si el bloque de temporada está y `lluvia.estado == "por_debajo"`, se resta
   **15** al `indice` de las estrategias con `demanda_agua == "alta"` y se añade
   un motivo. Ese 15 es **peso de diseño, no agronómico**.

Sin `contexto_reciente`, el motor funciona igual: solo no aplica la resta.

## Contrato de salida

```python
{
  "id": "actual" | "alternativa_1" | "alternativa_2",
  "titulo": "Rotación actual",
  "cultivos": ["..."],
  "demanda_agua": "alta" | "media" | "baja",
  "meses_criticos": [3, 4, 5],        # 1..12, provisional
  "indice": 42,                        # 0..100, orientativo
  "componentes": {"agua": 6.0, "diversidad": 3.3},
  "motivos": ["..."],
  "datos_faltantes": ["..."],
  "riesgos": ["..."],
  "provisional": True,
  "fuentes": []
}
```

`datos/rotaciones.json` (lo escribe `generar_rotaciones.py`):

```json
{"version": 1, "generado": "2026-11-06T10:00:00-04:00",
 "fuente_clima": "NASA POWER (reanálisis MERRA-2)",
 "fincas": [{"id": "constanza", "meses_secos": [2, 3, 4],
             "estrategias": [{"id": "actual", "titulo": "...", "cultivos": [],
                              "indice": 42, "componentes": {"agua": 6.0, "diversidad": 3.3},
                              "motivos": [], "datos_faltantes": [], "riesgos": [],
                              "provisional": true, "fuentes": []}]}]}
```

La interfaz (tarea 7) recalcula el índice con los deslizadores a partir de
`componentes`; por eso los componentes van en el JSON.

## Pasos

1. `CULTIVOS`: si existe `datos/cultivos.json` (tarea 8), úsalo; si no, tabla
   inline provisional. Cada entrada: `id`, `nombre`, `demanda_agua`,
   `meses_criticos`, `estado`, `fuente`. Lo no citable → `provisional`.
2. `ESTRATEGIAS`: `actual` (usa `finca["cultivo_actual"]`) y dos alternativas
   coherentes con clima tropical. Sin números de rendimiento, dosis ni fechas.
3. `meses_secos(climatologia)`: media por mes de `lluvia_mm_dia` sobre los años
   con dato; devuelve los 3 índices (1..12) con menor media.
4. `evaluar_rotaciones(finca, contexto_reciente=None, clima=None)`: calcula
   componentes, índice (`50·agua/10 + 50·diversidad/10`), resta por déficit y
   arma textos.
5. `generar_rotaciones.py`: lee `datos/fincas.json` y `datos/reciente.json` (si
   existe), llama al motor por finca y escribe `datos/rotaciones.json` y
   `datos/rotaciones.js` (`window.__ROTACIONES__ = {...}`) atómicos, igual que
   hace la tarea 2 con `reciente.js`. `--verificar` imprime sin escribir.
6. `docs/rotaciones.md`: tabla cultivo → demanda → meses críticos → fuente (o
   "sin fuente"), y las fórmulas con su etiqueta de heurística.
7. Tests (unittest):
   - 3 estrategias, ids únicos, `indice` en 0..100;
   - `meses_secos` con climatología sintética conocida;
   - agua baja cuando los meses críticos caen en los secos;
   - con contexto seco, la de demanda alta baja exactamente 15;
   - la de demanda baja no cambia;
   - `riesgos` y `datos_faltantes` no vacíos;
   - `provisional` es `True` mientras no haya fuentes.

## Criterios de aceptación

```bash
python3 -m unittest tests.test_rotaciones -v
python3 generar_rotaciones.py --verificar
python3 - <<'PY'
import json
d = json.load(open("datos/rotaciones.json"))
assert len(d["fincas"]) == 3
for f in d["fincas"]:
    assert 1 <= len(f["meses_secos"]) == 3
    assert len(f["estrategias"]) == 3
print("rotaciones.json OK")
PY
```

## Trampas

- No metas cifras de rendimiento, dosis ni fechas de siembra: no hay fuente.
- No importes `requests` ni leas archivos en `tools/rotaciones.py`.
- El clima sale de POWER; el contexto reciente de Open-Meteo. **No compares uno
  contra el otro**: el contexto solo dice "déficit" y penaliza.
- `climatologia` puede faltar: en ese caso `agua` y `diversidad` se calculan
  igual, pero `meses_secos` va vacío y se añade "sin climatología POWER".

## Si te bloqueas

Issue `Tarea 4 · <duda>`. Si no encuentras fuente citable, deja `provisional` y
anótalo en `docs/rotaciones.md`; no la elimines.
