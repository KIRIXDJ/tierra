# Tareas del equipo

## Cambio de regla (base de la demo)

- La demo funciona **sin internet** con datos precalculados en el repo.
- Encima va una capa **opcional** "Esta temporada" con datos recientes en vivo,
  con caché y respaldo. Sin red: último dato cacheado + su fecha + "sin conexión".
- Los datos de meses o años **solo** sirven para tendencia y estimación, no para
  la cosecha en curso. Por eso la capa nueva trabaja con 30 días + 7 de pronóstico.

## Reparto (5 bloques)

| # | Bloque | Entregables | Depende de |
|---|---|---|---|
| 1 | Climatología | `datos/fincas.json`, `tools/power_cliente.py` para traer POWER mensual 1991–2020 y las 3 fincas piloto | — |
| 2 | Temporada | `tools/reciente.py`, `actualizar_reciente.py`, `datos/reciente.json`, `datos/reciente.js` | 1 |
| 3 | Interfaz | chip "Finca", panel "Esta temporada", serie de 30 días con banda P25–P75, pronóstico, etiquetas de fuente y fecha | contrato de 2 |
| 4 | Motor de rotaciones | `tools/rotaciones.py` con 3 estrategias provisionales y `contextoReciente` opcional | contrato de 2 |
| 5 | QA | `tests/test_reciente.py` con casos: dato completo, parcial, sin red, fecha vieja | contrato de 2 |

Cada bloque se prueba por separado con `python3 -m unittest discover -s tests`
y se integra por PR a `main`. El bloque de QA debe hacerlo alguien distinto de
quien escribe el módulo.

## Quién hace qué

Roles por defecto; los nombres los pone el equipo. **Nadie empuja directo a
`main`**: cada rol trabaja en su rama y abre PR con el CI en verde.

| Rol | Persona | Rama | Entrega | Terminado cuando |
|---|---|---|---|---|
| A · Datos | (nombre) | `feat/datos-fincas` | `generar_fincas.py`, `datos/fincas.json` | `--verificar` imprime 3 fincas y el test de esquema pasa |
| B · Temporada | (nombre) | `feat/temporada` | `tools/reciente.py`, `actualizar_reciente.py`, `datos/reciente.json`/`.js` | corre con red, conserva caché sin red y sus tests pasan |
| C · Interfaz | (nombre) | `feat/ui-finca` | chip y panel "Esta temporada" en `web/index.html` | se ve con el fixture, sin `reciente.js` no rompe, `node --check` OK |
| D · Agronomía | (nombre) | `feat/rotaciones` | `tools/rotaciones.py` + fuentes | 3 estrategias con motivos/riesgos/provisional, con y sin contexto |
| E · QA | (nombre) | `test/reciente` | `tests/test_reciente.py` | 4 casos (completo, parcial, sin red, fecha vieja) verdes y checklist de textos |

### A · Datos y climatología (≈3 h)

1. Crear `datos/fincas.json` con las 3 fincas piloto (coordenadas en `validar_power.py`).
2. `generar_fincas.py` en la raíz: POWER mensual 1991–2020 por finca, reutilizando
   `tools/power_cliente.py` (no duplicar la descarga).
3. Escribir `climatologia.mensual` por año y mes; `null` donde falte.
4. `--verificar` que imprime las normales sin escribir.
5. Test de esquema: 3 fincas, 30 años, 12 meses, sin NaN.

### B · Temporada (≈4 h)

1. `tools/reciente.py`: percentil, ventana de 30 días, normal ponderada, banda
   P25–P75, anomalías, frescura y caché (funciones puras, sin red).
2. `actualizar_reciente.py`: `urllib`, 1 petición por finca, tolerante a fallos
   parciales, escritura atómica, código 1 si falla todo.
3. Generar `datos/reciente.json` y `datos/reciente.js`.
4. Pasarle a C un fixture con la forma exacta el primer día (no esperar al final).

### C · Interfaz (≈4 h)

1. Chip "Finca" en `#chips` y `<aside id="finca">` con selector.
2. Tarjeta: anomalías en lenguaje llano, canvas de 30 días con banda, pronóstico de 7.
3. Pie con fecha, fuente y "Open-Meteo · no NASA"; avisos fijos: no es monitoreo
   de parcela, no mezclar con 1984–2025.
4. `window.__RECIENTE__` opcional; `fetch` solo en http; sin datos, "sin datos recientes".
5. Al elegir finca, `volarA(lat, lon)`.

### D · Agronomía y motor (≈4 h)

1. Buscar 3 rotaciones con fuente citable; si no hay, `provisional` + `fuente: null`.
2. `tools/rotaciones.py`: `evaluar_rotaciones(finca, contexto_reciente=None)`.
3. Cada estrategia con `motivos`, `datos_faltantes`, `riesgos`, `provisional`.
4. Penalización por déficit hídrico documentada como peso de diseño.
5. Tests con y sin contexto.

### E · QA (≈3 h)

1. `tests/test_reciente.py` con los 4 casos, sin red, con fixtures.
2. Checklist de textos: nada de "monitoreo de parcela"; toda cifra con fuente;
   provisionales avisados.
3. Probar sin `datos/reciente.js` y con fecha vieja.
4. Revisar que el CI siga verde y que nadie haya roto `main`.

## Calendario (hoy 3 nov, entrega 14 nov)

| Fecha | Qué |
|---|---|
| 3 nov | Contratos cerrados, fixtures, ramas creadas |
| 4–5 nov | A y B producen datos; C maqueta con fixture; D investiga fuentes |
| 6–7 nov | Integración C+B; D motor; E pruebas |
| 8–9 nov | Offline (three.js/MediaPipe locales), textos, pulido |
| 10–11 nov | Elio si hay tiempo, y presentación/demo |
| 12–13 nov | Ensayo offline, capturas, video de respaldo |
| 14–15 nov | Evento y entrega |

## Reglas de trabajo en grupo

- Una rama por rol (`feat/...`), PR a `main`, CI verde, una revisión.
- Mensajes de commit en español, tipo `feat(tierra): ...`, un commit por tarea.
- Los contratos de `fincas.json` y `reciente.json` no se cambian sin avisar.
- Si alguien se bloquea más de 30 min, lo dice; no se queda callado.
- Reunión diaria de 15 min: qué hice, qué sigue, qué me bloquea.

## Contratos (no cambiar sin avisar)

`datos/fincas.json`

```json
{"version": 1, "fincas": [{
  "id": "constanza", "nombre": "Constanza", "pais": "República Dominicana",
  "lat": 18.91, "lon": -70.74, "zona_horaria": "America/Santo_Domingo",
  "cultivo_actual": "provisional",
  "climatologia": {
    "periodo": [1991, 2020],
    "fuente": "NASA POWER temporal/monthly/point (reanálisis MERRA-2)",
    "mensual": {"1991": {"lluvia_mm_dia": [12.0], "t2m": [23.1]}}
  }
}]}
```

`datos/reciente.json`

```json
{"version": 1, "actualizado": "2026-11-02T16:40:00-04:00",
 "fuente": {"nombre": "Open-Meteo (ECMWF/ERA5-Land)", "no_nasa": true},
 "ventana": {"inicio": "2026-10-03", "fin": "2026-11-01", "dias": 30},
 "avisos": [],
 "fincas": [{
   "id": "constanza", "nombre": "Constanza",
   "lluvia": {"30d_mm": 12.4, "normal_mm": 45.1, "pct": -72,
              "banda": [30.2, 61.7], "estado": "por_debajo"},
   "temperatura": {"media": 24.1, "normal": 23.5, "delta": 0.6,
                   "banda": [22.9, 24.2], "estado": "normal"},
   "humedad_raiz": {"valor": 0.28, "unidad": "m³/m³", "cambio_7d": -0.02,
                    "banda": null, "nota": "sin climatología comparable"},
   "serie_30d": [{"fecha": "2026-10-03", "lluvia_mm": 0.0,
                  "tmax": 25.1, "tmin": 17.2, "humedad": 0.29}],
   "pronostico": [{"fecha": "2026-11-03", "lluvia_mm": 3.2,
                   "tmax": 26.0, "tmin": 17.4}]
 }]}
```

Falta un dato = `null`, y la interfaz dice "sin dato". Nunca se rellena a ojo.

## Definiciones de anomalía

- **Ventana**: 30 días completos, `fin` = ayer en la zona horaria de la finca,
  `inicio` = `fin − 29`.
- **Normal de lluvia**: suma de las normales mensuales POWER (mm/día) ponderadas
  por los días de cada mes dentro de la ventana.
- **Banda**: P25–P75 de esa misma suma calculada año por año 1991–2020.
- **Estado**: `< P25` → `por_debajo`; `> P75` → `por_encima`; resto → `normal`.
- **Humedad de raíz**: media de 7 días y cambio contra los 7 anteriores.
  Sin banda: no hay climatología homogénea de esa variable; se dice, no se inventa.

## Pendiente

- Elio (asistente): diseño listo, sin código. Responde solo con el contexto
  estructurado que la app le entrega, cita fuente y no controla actuadores.
- Tarea A completa: catálogo de cultivos con fuente citable y las pantallas de
  comparación de las 3 rotaciones.
- Localizar three.js y MediaPipe para que la demo sea 100 % offline.
