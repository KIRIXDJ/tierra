# Tarea 8 · Cultivos con fuente citable

**Entrega:** `datos/cultivos.json` con 6–8 cultivos de la zona y
`docs/cultivos-fuentes.md` con la cita de cada dato. **≈3 h** (la mitad es buscar
y leer las fuentes). Es lo que quita el `provisional` de la tarea 4.

**Rama:** `tarea/8-cultivos` · **Commit:** `feat(cultivos): tabla con fuentes y revisión`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/8-cultivos
# ... trabajas ...
git add datos/cultivos.json docs/cultivos-fuentes.md
git commit -m "feat(cultivos): tabla con fuentes y revisión"
git push -u origin tarea/8-cultivos
# luego abre el PR en GitHub: base main <- tarea/8-cultivos
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/8-cultivos`.

## Permitido tocar

- `datos/cultivos.json` (nuevo)
- `docs/cultivos-fuentes.md` (nuevo)
- `tests/test_cultivos.py` (nuevo)

## Prohibido

`web/`, `tools/`, `datos/fincas.json`, `datos/reciente.json`.

## Regla que no se negocia

Cada dato agronómico necesita **fuente citable**: FAO, ministerio/institución de
extensión, manual de cultivo, artículo revisado. Si no la encuentras:

```json
"estado": "provisional", "fuente": null, "nota": "no encontrado en fuente citable"
```

No inventes valores, no "estimes por lo que se sabe", no copies de un blog sin
autor. Un cultivo sin fuente puede entrar, pero marcado.

## Contrato

```json
{
  "version": 1,
  "revisado_por": null,
  "fecha_revision": null,
  "fincas_objetivo": ["constanza", "azua", "san_francisco_de_macoris"],
  "cultivos": [
    {
      "id": "maiz",
      "nombre": "Maíz",
      "demanda_agua": "alta",
      "meses_criticos": [5, 6, 7, 8],
      "ciclo_dias": null,
      "estado": "provisional",
      "fuente": null,
      "nota": "demanda de agua y ventana tomadas de ..."
    }
  ]
}
```

- `demanda_agua`: `"alta" | "media" | "baja"`.
- `meses_criticos`: meses 1..12 en que el cultivo necesita agua; al menos uno.
- `ciclo_dias`: `null` si no hay fuente; no lo estimes.
- `revisado_por`: nombre del agrónomo/profesor, `fecha_revision` ISO; `null`
  mientras no haya revisión. **Sin esto, todo sigue `provisional` en la app**.
- 6 a 8 cultivos propios de la zona de las fincas piloto (República Dominicana:
  maíz, frijol, yuca, plátano, sorgo, maní, etc.), priorizando los que ya
  aparecen en el cultivo actual.

## Pasos

1. Lista los 6–8 cultivos y, para cada uno, busca una fuente con `demanda_agua`
   y ventana de necesidad de agua.
2. Rellena `datos/cultivos.json`. Lo que no tenga fuente, `provisional`.
3. `docs/cultivos-fuentes.md`: tabla cultivo → dato → fuente (URL/página) →
   quién revisó. Aquí van las citas completas.
4. `tests/test_cultivos.py` (unittest, sin red):
   - 6–8 cultivos, ids únicos;
   - `demanda_agua` en el enum;
   - `meses_criticos` no vacío y dentro de 1..12;
   - todo cultivo con `estado != "provisional"` tiene `fuente` no nula;
   - si `revisado_por` es nulo, hay al menos un `provisional` (coherencia).
5. Pide la revisión a un agrónomo o profesor y anota `revisado_por` y la fecha
   en un PR aparte (no lo inventes).

## Criterios de aceptación

```bash
python3 -m unittest tests.test_cultivos -v
python3 - <<'PY'
import json
d = json.load(open("datos/cultivos.json"))
assert 6 <= len(d["cultivos"]) <= 8
prov = [c["id"] for c in d["cultivos"] if c["estado"] == "provisional"]
print("cultivos:", len(d["cultivos"]), "| provisionales:", prov)
PY
```

Pega la salida en el PR y di cuántos quedaron provisionales y por qué.

## Trampas

- Una fuente que no dice el dato no es fuente: no la pongas para "cumplir".
- No mezcles regiones: si el dato es de clima templado, no sirve para Constanza.
- No cambies `revisado_por` a un nombre sin permiso de esa persona.

## Si te bloqueas

Issue `Tarea 8 · <cultivo> sin fuente`. Se entrega igual, marcado.
