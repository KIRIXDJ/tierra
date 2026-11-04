# Tarea 4 · Motor de rotaciones con contexto reciente

**Entrega:** `tools/rotaciones.py` con `evaluar_rotaciones(finca, contexto_reciente=None)`
y 3 estrategias (incluida la actual). **≈4 h.** No depende del código de la
tarea 2: solo del contrato `reciente.json`.

**Rama:** `tarea/4-rotaciones` · **Commit:** `feat(rotaciones): motor con contexto de temporada`

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
git commit -m "feat(rotaciones): motor con contexto de temporada"
git push -u origin tarea/4-rotaciones
# luego abre el PR en GitHub: base main <- tarea/4-rotaciones
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/4-rotaciones`. Si ya empujaste a `main` por error, no fuerces:
avisa y se revierte.


## Permitido tocar

- `tools/rotaciones.py` (nuevo)
- `tests/test_rotaciones.py` (nuevo)
- `docs/rotaciones.md` (nuevo: fuentes de cada parámetro)

## Prohibido

`web/`, `datos/`, `tools/reciente.py`, `tools/power_cliente.py`, `AGENTS.md`.

## Contrato de salida

`evaluar_rotaciones` devuelve **siempre** una lista de 3 diccionarios:

```python
{
  "id": "actual" | "alternativa_1" | "alternativa_2",
  "titulo": "Rotación actual",
  "cultivos": ["..."],
  "demanda_agua": "alta" | "media" | "baja",
  "indice": 42,                    # 0..100, orientativo
  "motivos": ["..."],              # por qué se sugiere
  "datos_faltantes": ["..."],      # qué falta para decidir mejor
  "riesgos": ["..."],              # qué revisar con un agrónomo
  "provisional": True,
  "fuentes": []                    # [] si no hay fuente citable
}
```

Reglas:

- Funciona **con y sin** `contexto_reciente`. Sin él, no hay penalización.
- `contexto_reciente` es el bloque de **una** finca de `datos/reciente.json`
  (`{"lluvia": {"estado": "por_debajo", ...}, "humedad_raiz": {...}}`), no el
  archivo completo.
- Penalización documentada: si `contexto_reciente["lluvia"]["estado"] == "por_debajo"`,
  a las estrategias con `demanda_agua == "alta"` se les resta **15** puntos y se
  añade un motivo. Ese 15 es **peso de diseño, no agronómico**: dilo en el
  código y en `docs/rotaciones.md`.
- `indice` siempre entre 0 y 100.
- Si no hay fuente para un parámetro: `"provisional": true`, `"fuentes": []` y
  un motivo "parámetro provisional, validar con agrónomo".

## Pasos

1. Crea la tabla `CULTIVOS` (lista de dicts con `id`, `nombre`, `demanda_agua`,
   `estado`, `fuente`). Todo lo que no puedas citar va `estado="provisional"`,
   `fuente=None`.
2. Define `ESTRATEGIAS`: `actual` (la del `cultivo_actual` de la finca) y dos
   alternativas coherentes con clima tropical húmedo/seco. Sin números
   agronómicos inventados: solo composición, demanda de agua y rotación.
3. Implementa `indice_base(estrategia)` con una fórmula simple y explícita
   (por ejemplo 50, +10 si toda la demanda es baja, −10 si alguna es alta).
   Documéntala en el docstring: es **orientativa**.
4. Implementa la penalización por déficit y los textos de `motivos`,
   `datos_faltantes` y `riesgos` (estos dos últimos siempre con al menos una
   entrada: textura de suelo, precios, rendimiento histórico, etc.).
5. `docs/rotaciones.md`: tabla de cultivos con `fuente` o "sin fuente", y la
   explicación del índice y del 15.
6. `tests/test_rotaciones.py` (unittest):
   - 3 estrategias, ids únicos, `indice` en 0..100;
   - sin contexto y con contexto seco: la de demanda alta baja exactamente 15;
   - la de demanda baja no cambia;
   - todas traen `riesgos` y `datos_faltantes` no vacíos;
   - `provisional` es `True` mientras no haya fuentes.

## Criterios de aceptación

```bash
python3 -m unittest tests.test_rotaciones -v
python3 - <<'PY'
from tools.rotaciones import evaluar_rotaciones
finca = {"id": "constanza", "cultivo_actual": "provisional"}
for r in evaluar_rotaciones(finca):
    print(r["id"], r["indice"], r["demanda_agua"], r["provisional"])
ctx = {"lluvia": {"estado": "por_debajo"}, "humedad_raiz": {"valor": 0.2}}
for r in evaluar_rotaciones(finca, ctx):
    print(r["id"], r["indice"])
PY
```

La segunda salida debe mostrar la resta de 15 solo en las de demanda alta.

## Trampas

- No metas cifras de rendimiento, dosis ni fechas de siembra: no hay fuente.
- No importes `requests` ni leas archivos: el motor es puro.
- No devuelvas `float("nan")` ni `None` en `indice`.
- `contexto_reciente` puede venir con campos `null`: trátalo como "sin dato",
  no como "normal".

## Si te bloqueas

Issue `Tarea 4 · <duda>`. Si no encuentras fuente citable para una rotación,
déjala `provisional` y escríbelo en `docs/rotaciones.md`; no la elimines.
