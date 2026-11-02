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
