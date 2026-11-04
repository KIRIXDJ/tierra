# Tarea 10 · Elio, modo local (sin IA)

**Entrega:** `web/elio.js` con respuestas deterministas sobre los datos que ya
calculó la app, y `tests/elio.mjs` para probarlo con Node. **≈4 h.**
Es el asistente Elio en su versión honesta: no llama a ningún modelo, no usa
claves y no controla nada.

**Rama:** `tarea/10-elio` · **Commit:** `feat(elio): respuestas locales sobre los datos`

## Paso 0 · Crea tu rama (obligatorio)

`main` está protegida: **el push directo se rechaza**. Trabaja en tu rama y
entrega por PR. Copia y pega:

```bash
git clone https://github.com/KIRIXDJ/tierra.git   # si aún no lo tienes
cd tierra
git checkout main && git pull                     # parte de main al día
git checkout -b tarea/10-elio
# ... trabajas ...
git add web/elio.js tests/elio.mjs web/index.html .github/workflows/pruebas.yml
git commit -m "feat(elio): respuestas locales sobre los datos"
git push -u origin tarea/10-elio
# luego abre el PR en GitHub: base main <- tarea/10-elio
```

Si tu IA te propone trabajar en `main` o empujar a `main`, dile que **no**:
la rama es `tarea/10-elio`.

## Permitido tocar

- `web/elio.js` (nuevo)
- `tests/elio.mjs` (nuevo)
- `web/index.html` — **solo** dos añadidos: `<div id="elio">` y
  `<script src="web/elio.js"></script>`. Nada más.
- `.github/workflows/pruebas.yml` — solo añadir `node tests/elio.mjs`.

## Prohibido

Reescribir el módulo del globo, tocar `tools/`, `datos/`, cambiar el estilo
global, añadir dependencias o CDN.

## Antes de empezar

`web/index.html` lo tocan las tareas 3 y 7. **Integra después de la 7**, con
`main` actualizado, y limita tu diff a esas dos líneas. Si hace falta más,
háblalo con quien lleve la interfaz.

## Principios (los mismos del diseño)

1. Elio responde **solo** con lo que hay en `window.__ROTACIONES__`,
   `window.__RECIENTE__` y `window.__FINCAS__`.
2. Si el dato no está: **"No tengo ese dato"**, sin estimar ni inventar.
3. Cita la fuente de cada cifra: "POWER (reanálisis)", "Open-Meteo (no NASA)",
   "tabla de cultivos provisional".
4. Recuerda que es apoyo y que se valida con un agrónomo local.
5. No controla dispositivos, sensores ni riego. Si se lo piden: "eso no lo hago".

## Qué debe responder (router de intenciones)

| Pregunta | De dónde sale |
|---|---|
| "¿cómo va la temporada?" | `reciente.fincas[i].lluvia` + `temperatura` |
| "¿cuánta lluvia ha caído?" | `lluvia.30d_mm` vs `normal_mm` |
| "¿qué rotación me conviene?" | `rotaciones.fincas[i].estrategias` ordenadas por `indice` |
| "¿por qué esa?" | `motivos` de la estrategia |
| "¿qué riesgos tiene?" | `riesgos` + `datos_faltantes` |
| "¿qué es el NDVI / la evapotranspiración?" | glosario fijo en el código |
| "¿está seco?" | `lluvia.estado` |
| "activa el riego" | "No controlo dispositivos en esta fase" |
| cualquier otra | "No tengo ese dato. Puedo hablarte de la temporada y de las rotaciones" |

- La finca activa es la del selector de la pestaña Finca; si no hay, la primera.
- Respuestas cortas (1–3 frases), sin jerga sin explicar.

## Estructura de `web/elio.js`

```js
// window.Elio = { responder(pregunta, contexto), montar(documento) }
// responder es pura: recibe el contexto y devuelve texto. Los tests la usan sin DOM.
window.Elio = { responder, montar };
```

`contexto = { reciente, rotaciones, fincaId }`. `responder` no toca el DOM; así
se prueba con Node.

## Tests (`tests/elio.mjs`, sin DOM)

Con `node tests/elio.mjs` debe imprimir `OK` y salir con código 0:

1. temporada con datos → menciona mm, % y la fuente "Open-Meteo";
2. rotación → devuelve la de mayor `indice` y cita "índice orientativo";
3. datos ausentes → "No tengo ese dato";
4. "activa el riego" → "No controlo dispositivos";
5. cifra siempre con fuente (assert de que la respuesta contiene "POWER" u
   "Open-Meteo" cuando da un número).

## Criterios de aceptación

```bash
node tests/elio.mjs                 # imprime OK
node --check web/elio.js
python3 -m unittest discover -s tests   # no debe empeorar
```

A mano: abrir `web/`, escribir 3 preguntas y comprobar que responde; borrar
`datos/reciente.js` y comprobar que dice "no tengo ese dato", no que revienta.

## Trampas

- No metas una clave de API ni un `fetch` a un modelo: esta versión es local.
- No inventes cifras de ejemplo en el HTML: todas salen del contexto.
- Si `componentes` o `indice` son `null`, no ordenes como si fueran 0.
- No toques el CSS global: el panel de Elio va con clases propias.

## Si te bloqueas

Issue `Tarea 10 · <duda>`. Si el contexto no alcanza para una pregunta,
la respuesta correcta es "no tengo ese dato".
