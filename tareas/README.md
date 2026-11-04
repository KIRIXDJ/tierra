# Tareas — instrucciones para agentes y personas

Cada tarea vive en su propio archivo y es **autosuficiente**: si te toca la
tarea 2, lee `02-temporada.md` y nada más (además de `AGENTS.md` y
`00-contratos.md`). No necesitas el contexto de la conversación que la originó.

| Tarea | Archivo | Rama | Toca | No toca |
|---|---|---|---|---|
| 1 · Datos | [01-datos.md](01-datos.md) | `tarea/1-datos` | `generar_fincas.py`, `datos/fincas.json`, `tools/power_cliente.py` (solo añadir), `tests/test_fincas.py`, `tests/fixtures/power_mensual.json` | `web/`, `tools/tendencia.py`, `tools/malla_global.py`, `tests/test_power_cliente.py` |
| 2 · Temporada | [02-temporada.md](02-temporada.md) | `tarea/2-temporada` | `tools/reciente.py`, `actualizar_reciente.py`, `datos/reciente.json`, `datos/reciente.js`, `tests/test_reciente.py`, `tests/fixtures/openmeteo_*.json` | `web/`, `datos/fincas.json`, `tools/rotaciones.py` |
| 3 · Interfaz | [03-ui.md](03-ui.md) | `tarea/3-ui` | `web/index.html` | `tools/`, `datos/`, `tests/` |
| 4 · Rotaciones | [04-rotaciones.md](04-rotaciones.md) | `tarea/4-rotaciones` | `tools/rotaciones.py`, `generar_rotaciones.py`, `datos/rotaciones.json`/`.js`, `tests/test_rotaciones.py`, `docs/rotaciones.md` | `web/`, `datos/fincas.json`, `tools/reciente.py` |
| 5 · QA | [05-qa.md](05-qa.md) | `tarea/5-qa` | `tests/test_reciente_casos.py`, `tests/fixtures/reciente_*.json`, `docs/revision-textos.md` | los archivos de código de las otras tareas |
| 6 · Demo | [06-demo.md](06-demo.md) | `tarea/6-demo` | `docs/demo.md` | todo lo demás |
| 7 · Rotaciones UI | [07-rotaciones-ui.md](07-rotaciones-ui.md) | `tarea/7-rotaciones-ui` | `web/index.html` (después de la 3) | `tools/`, `datos/`, `tests/` |
| 8 · Cultivos | [08-cultivos.md](08-cultivos.md) | `tarea/8-cultivos` | `datos/cultivos.json`, `docs/cultivos-fuentes.md`, `tests/test_cultivos.py` | `web/`, `tools/`, `datos/fincas.json` |
| 10 · Elio local | [10-elio.md](10-elio.md) | `tarea/10-elio` | `web/elio.js`, `tests/elio.mjs`, 2 líneas en `web/index.html` | el módulo del globo, `tools/`, `datos/` |

## Protocolo (obligatorio)

1. **Rama**: cada archivo de tarea empieza con "Paso 0 · Crea tu rama", con el
   comando exacto. Resumen: `git checkout main && git pull` y
   `git checkout -b tarea/N-slug`. Nunca trabajes en `main`.
2. **Alcance**: toca solo la columna "Toca". Si necesitas otro archivo, **para**
   y abre un issue `Tarea N · necesito tocar <archivo>`. No lo toques "de paso".
3. **Contrato**: los formatos de `00-contratos.md` son fijos. Si algo no encaja,
   es un issue, no un cambio silencioso.
4. **Aceptación**: corre los comandos de "Criterios de aceptación" de tu archivo
   y pega la salida en el PR. Sin salida, el PR no se revisa.
5. **Commit**: uno solo, en español, con el prefijo que indica tu archivo.
6. **PR**: título `Tarea N · <resumen>`; descripción con qué hiciste, comandos
   corridos y qué quedó pendiente. Para la tarea 3, además una captura.
7. **Prohibido en todas**: reformatear código ajeno, renombrar archivos,
   actualizar dependencias, commitear `.env` o datos personales, tocar `main`,
   meter claves de API en el HTML/JS, y "arreglar" otra tarea.

## Reglas de contenido

- Nada agronómico inventado: si no hay fuente, `"estado": "provisional"` y
  `"fuente": null`, y la interfaz lo avisa.
- Todo dato no-NASA se rotula (Open-Meteo/ERA5).
- Los fixtures de prueba pueden llevar números inventados **porque no se
  muestran en la app**, pero el JSON real no.
- El texto de la app no dice "monitoreo de parcela": son estimaciones de celda.

## Orden y dependencias

```
T1 (datos) ──> T2 (temporada) ──> T3 (interfaz)
                    └──────────> T5 (QA)
T4 (rotaciones) usa el contrato de T2, no su código
T6 (demo) depende de que T3 esté integrada
```

T3 puede empezar el día 1 con `tests/fixtures/reciente_ejemplo.json`, que T2
entrega antes de terminar su pipeline.

**`web/index.html` es un solo archivo**: lo tocan las tareas 3, 7 y 9. Se
integran en orden 3 → 7 → 9, o los hace la misma persona. Si dos PR abiertos lo
tocan a la vez, se pisan.

## Descartado

- **T9 · Demo sin internet**: el producto es monitoreo en línea, no un modo
  offline. Riesgo que queda anotado, sin tarea: three.js y las texturas vienen
  de un CDN, y si falla la red la app no arranca (no es "offline", es no
  depender de un CDN para pintar). El FDR ya está implementado: no se rehace.
