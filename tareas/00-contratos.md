# Contratos de datos (fijos)

Cambiar cualquiera de estos formatos requiere avisar al grupo y actualizar este
archivo en el mismo PR. Los consumidores (interfaz, motor, QA) se escriben
contra esto, no contra el código de quien lo produce.

## `datos/fincas.json`

Lo produce la tarea 1. Se commitea (es dato precalculado para la demo offline).

```json
{
  "version": 1,
  "generado": "2026-11-04T10:00:00-04:00",
  "fuente": "NASA POWER temporal/monthly/point · community AG · reanálisis MERRA-2",
  "periodo": [1991, 2020],
  "fincas": [
    {
      "id": "constanza",
      "nombre": "Constanza",
      "pais": "República Dominicana",
      "lat": 18.91,
      "lon": -70.74,
      "zona_horaria": "America/Santo_Domingo",
      "cultivo_actual": "provisional",
      "climatologia": {
        "periodo": [1991, 2020],
        "fuente": "NASA POWER (reanálisis MERRA-2)",
        "mensual": {
          "1991": {
            "lluvia_mm_dia": [12.0, 9.4, 11.2, 13.0, 14.1, 9.9, 8.2, 9.1, 11.0, 12.8, 13.9, 12.2],
            "t2m": [22.1, 22.3, 22.9, 23.4, 23.9, 24.3, 24.5, 24.4, 24.1, 23.6, 22.9, 22.2]
          }
        }
      }
    }
  ]
}
```

- `lluvia_mm_dia`: 12 valores, **tasa media diaria en mm/día** (así la devuelve
  POWER). Para acumular un mes: `valor × días_del_mes`.
- `t2m`: 12 valores, media mensual en °C.
- `null` cuando POWER no da dato (relleno `-999`). Nunca `NaN` ni `0` para hueco.
- `mensual` cubre los 30 años de `periodo`, sin huecos de año.

## `datos/reciente.json`

Lo produce la tarea 2. Se commitea (es el snapshot offline).

```json
{
  "version": 1,
  "actualizado": "2026-11-04T18:30:00-04:00",
  "fuente": {
    "nombre": "Open-Meteo (ECMWF / ERA5-Land)",
    "url": "https://api.open-meteo.com/v1/forecast",
    "no_nasa": true,
    "nota": "No es NASA ni un sensor en la parcela: es modelo."
  },
  "ventana": {"inicio": "2026-10-05", "fin": "2026-11-03", "dias": 30},
  "avisos": [],
  "fincas": [
    {
      "id": "constanza",
      "nombre": "Constanza",
      "lluvia": {
        "30d_mm": 12.4, "normal_mm": 45.1, "pct": -72,
        "banda": [30.2, 61.7], "estado": "por_debajo"
      },
      "temperatura": {
        "media": 24.1, "normal": 23.5, "delta": 0.6,
        "banda": [22.9, 24.2], "estado": "normal"
      },
      "humedad_raiz": {
        "valor": 0.28, "unidad": "m³/m³", "cambio_7d": -0.02,
        "banda": null, "nota": "sin climatología comparable"
      },
      "serie_30d": [
        {"fecha": "2026-10-05", "lluvia_mm": 0.0, "tmax": 25.1, "tmin": 17.2, "humedad": 0.29}
      ],
      "pronostico": [
        {"fecha": "2026-11-04", "lluvia_mm": 3.2, "tmax": 26.0, "tmin": 17.4}
      ]
    }
  ]
}
```

Reglas:

- `actualizado`: ISO 8601 **con offset** de la zona de la finca.
- `ventana`: 30 días completos; `fin` = ayer, `inicio` = `fin − 29`.
- `estado`: `"por_debajo"` (< P25), `"normal"` (P25–P75), `"por_encima"` (> P75).
- Falta un dato → `null` en el campo, y se añade una frase a `avisos`.
- `serie_30d`: exactamente 30 entradas, una por día, aunque falte el valor.
- `pronostico`: 7 entradas; si no hay pronóstico, `[]` + aviso.
- `humedad_raiz.banda` siempre `null` (no hay climatología homogénea).

## `datos/reciente.js`

Espejo del JSON para poder abrirlo con `file://`:

```js
window.__RECIENTE__ = {"version": 1, "actualizado": "..." /* mismo objeto */};
```

## Definiciones de anomalía

- **Ventana**: 30 días completos, `fin = ayer` en la zona de la finca.
- **Normal de lluvia**: suma de `lluvia_mm_dia` de cada mes, ponderada por los
  días de ese mes dentro de la ventana (se cruza de mes, no se redondea).
- **Banda**: P25 y P75 de esa misma suma calculada año por año en `periodo`.
- **Temperatura**: media ponderada igual; `delta = media − normal`.
- **Humedad**: media de los últimos 7 días; `cambio_7d` contra los 7 anteriores.
  Sin banda, a propósito.

## Fixtures

- `tests/fixtures/reciente_ejemplo.json`: lo entrega la tarea 2 el día 1 para
  que la tarea 3 maquete sin esperar. Forma idéntica al JSON real.
- Los fixtures pueden llevar números inventados: **no se muestran en la app**.
