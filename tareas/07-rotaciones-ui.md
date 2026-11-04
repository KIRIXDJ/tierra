# Tarea 7 · Pestaña Rotaciones y prioridades del agricultor

**Entrega:** pestaña **Rotaciones** en `web/index.html`: 3 tarjetas de estrategia
con motivos, datos faltantes y riesgos, más los deslizadores de prioridades.
**≈5 h.** Depende de la tarea 4 (`datos/rotaciones.json` y `datos/rotaciones.js`)
y de la tarea 3 (mismo archivo: se integra **después**).

**Rama:** `tarea/7-rotaciones-ui` · **Commit:** `feat(ui): pestaña Rotaciones con prioridades`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/7-rotaciones-ui
# ... trabajas ...
git add web/index.html
git commit -m "feat(ui): pestaña Rotaciones con prioridades"
git push -u origin tarea/7-rotaciones-ui
# luego abre el PR en GitHub: base main <- tarea/7-rotaciones-ui
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/7-rotaciones-ui`. Si ya empujaste a `main` por error, no fuerces:
avisa y se revierte.

## Permitido tocar

- `web/index.html` (**solo** este archivo)

## Prohibido

`tools/`, `datos/`, `tests/`, `docs/`, `AGENTS.md`. No añadas librerías ni CDN.

## Antes de empezar: el archivo es compartido

`web/index.html` es un solo archivo y lo tocan las tareas 3, 7 y 9. **No abras
tu PR hasta que la tarea 3 esté mezclada en `main`**, y parte de `main`
actualizado. Si las dos están abiertas a la vez, se pisan. Orden: 3 → 7 → 9.
Consejo: una sola persona (Oscar) hace 3 y 7 seguidas.

## Qué construir

1. Botón `id="rotaciones-boton"` en `#chips`, texto **Rotaciones**.
2. `<aside id="rotaciones" hidden>` con:
   - `<input type="range" id="peso-agua">` y `id="peso-diversidad"`
     (0 a 10, etiquetados "Ahorrar agua" y "Diversificar");
   - `<div id="rotaciones-tarjetas">` con 3 tarjetas;
   - `<div id="rotaciones-pie">` con fuente y fecha.
3. Datos: `window.__ROTACIONES__` (lo genera la tarea 4). Si falta, la pestaña
   dice "sin datos de rotaciones" y no rompe nada.
4. Cálculo del índice **en el cliente**, a partir de `componentes`:
   `indice = 100 × (peso_agua·agua + peso_diversidad·diversidad) / (10·(peso_agua+peso_diversidad))`.
   Es aritmética sobre lo que ya calculó el motor; no inventes componentes.
5. Cada tarjeta muestra:
   - título, cultivos, `indice` (0–100) y una barra;
   - **Por qué se sugiere** (`motivos`), **qué falta** (`datos_faltantes`) y
     **qué revisar con un agrónomo** (`riesgos`), siempre visibles o en un
     `<details>`;
   - si `provisional` o `fuentes` vacío: insignia **"provisional, validar con
     agrónomo"**.
6. Aviso fijo al pie: "Índice orientativo. No reemplaza el juicio del agricultor
   ni de un agrónomo local."
7. Escenario (opcional si sobra tiempo): un `range` de lluvia ±20 % que suma o
   resta al componente `agua` según una regla **documentada en el código**
   (`shortcut: ajuste lineal de diseño, no modelo agronómico`). Si no se hace,
   se dice en el PR.

## Estados que hay que cubrir

| Caso | Qué se ve |
|---|---|
| Datos completos | 3 tarjetas ordenadas por índice; mover un deslizador reordena |
| Sin `window.__ROTACIONES__` | "sin datos de rotaciones" |
| Estrategia provisional | insignia visible en su tarjeta |
| Una estrategia sin `componentes` | se muestra sin índice y con "sin dato" |

## Criterios de aceptación

```bash
python3 - <<'PY'
import pathlib, re
html = pathlib.Path("web/index.html").read_text(encoding="utf-8")
mod = re.search(r'<script type="module">(.*?)</script>', html, re.S).group(1)
pathlib.Path("/tmp/modulo.mjs").write_text(mod, encoding="utf-8")
PY
node --check /tmp/modulo.mjs
python3 -m unittest discover -s tests        # no debe empeorar
```

A mano, con captura en el PR:

1. Con `datos/rotaciones.js` presente: 3 tarjetas, motivos/riesgos visibles,
   insignia provisional.
2. Mover "Ahorrar agua" al máximo: cambia el orden o el índice de forma visible.
3. Sin `datos/rotaciones.js`: la pestaña abre y dice "sin datos de rotaciones".
4. Teclado: los deslizadores se mueven con flechas y tienen `<label>`.

## Trampas

- No dupliques el panel de "Finca": usa un `aside` nuevo y el mismo CSS.
- El canvas/panel mide 0 si está `hidden`: pinta al mostrarlo.
- No escribas textos agronómicos nuevos: usa `motivos`/`riesgos` del JSON.
- No reordenes por un índice que tú inventes: usa `componentes`.
- Si `componentes.agua` es `null`, no lo trates como 0.

## Si te bloqueas

Issue `Tarea 7 · <duda>`. Si la tarea 4 no entrega `rotaciones.json`, no
inventes estrategias: abre el issue y espera el archivo.
