# Rotaciones: fuentes y fórmulas

Motor: `tools/rotaciones.py`. Generador: `generar_rotaciones.py` →
`datos/rotaciones.json` y `datos/rotaciones.js`.

El motor **no es agronomía**: es un ejercicio de diseño para ordenar estrategias
con la climatología de la finca. Los puntajes son orientativos y no sustituyen
la recomendación de un agrónomo. No incluye rendimientos, dosis ni fechas de
siembra.

## Fuentes

| Dato | Fuente | Uso |
|---|---|---|
| Lluvia mensual 1991–2020 | **NASA POWER** (reanálisis MERRA-2), `datos/fincas.json` | Meses secos de la finca |
| Temporada reciente | **Open-Meteo / ERA5** (no NASA), `datos/reciente.json` | Solo el estado `por_debajo`; no se compara con POWER |
| Demanda y meses críticos | `datos/cultivos.json` (tarea 8) o tabla provisional | Componentes `agua` y `diversidad` |

Regla del repo: una anomalía solo se calcula contra la normal de **la misma
fuente**. Por eso el motor no resta ERA5 contra POWER: el contexto reciente solo
dice si hubo déficit y, si lo hubo, penaliza a las estrategias de demanda alta.

### Meses secos

Se calculan, no se escriben a mano. Para cada mes (1..12) se promedia
`lluvia_mm_dia` sobre los años con dato en `climatologia.mensual`; se eligen los
**3 meses con menor media** (desempate por número de mes) y se devuelven en
orden ascendente. Si falta la climatología, la lista va vacía y el JSON lo
declara en `datos_faltantes`.

## Fórmulas (heurísticas de diseño)

| Componente | Fórmula | Rango |
|---|---|---|
| `agua` | `10 − 2.5 × \|meses_criticos ∩ meses_secos\|` | 0..10 |
| `diversidad` | `10 × cultivos_distintos / 3` | 0..10 |
| `indice` | `50 × agua / 10 + 50 × diversidad / 10` = `5·agua + 5·diversidad` | 0..100 |
| Déficit | `−15` al `indice` si `lluvia.estado == "por_debajo"` y `demanda_agua == "alta"` | — |

- El **2.5** y el **15** son pesos de diseño, no parámetros agronómicos. El 15
  queda acotado a 0..100 después de restar.
- La `diversidad` es aritmética: cuenta cultivos distintos en la estrategia,
  saturada a 3 cultivos.
- La `demanda_agua` de una estrategia es la **más alta** de sus cultivos; los
  `meses_criticos` son la **unión** de los de sus cultivos.
- La interfaz (tarea 7) recalcula el índice con deslizadores a partir de
  `componentes`; por eso ambos componentes van en el JSON.

## Cultivos de respaldo (provisional)

Mientras no exista `datos/cultivos.json` (tarea 8), el motor usa esta tabla
interna. **Ningún valor tiene fuente citable**: todos son `provisional`,
`fuente: null` y la app debe avisarlo.

| Cultivo | `id` | Demanda de agua | Meses críticos | Fuente |
|---|---|---|---|---|
| Maíz | `maiz` | alta | 5, 6, 7, 8 | sin fuente |
| Frijol | `frijol` | media | 5, 6, 7 | sin fuente |
| Yuca | `yuca` | baja | 6, 7, 8, 9 | sin fuente |
| Plátano | `platano` | alta | 1–12 | sin fuente |
| Sorgo | `sorgo` | baja | 5, 6, 7, 8 | sin fuente |
| Maní | `mani` | media | 6, 7, 8 | sin fuente |

Cuando exista la tabla con fuentes, el generador la lee de `datos/cultivos.json`
y el `provisional` desaparece solo para los cultivos con `fuente` no nula.

## Estrategias

- `actual`: usa `finca["cultivo_actual"]`. Si viene vacío o como
  `"provisional"`, la estrategia queda sin cultivos y lo anota en
  `datos_faltantes`.
- `alternativa_1`: combinación preferida `maiz + frijol`, completada con la
  tabla disponible.
- `alternativa_2`: combinación preferida `yuca + mani + sorgo`, completada con
  la tabla disponible.

Las combinaciones son una selección de diseño; no son una recomendación de
rotación ni una afirmación sobre rendimiento.

## Salida

`datos/rotaciones.json`:

```json
{
  "version": 1,
  "generado": "2026-11-06T10:00:00-04:00",
  "fuente_clima": "NASA POWER (reanálisis MERRA-2)",
  "fincas": [
    {
      "id": "constanza",
      "meses_secos": [2, 3, 4],
      "estrategias": [
        {
          "id": "actual",
          "titulo": "Rotación actual",
          "cultivos": [],
          "demanda_agua": "media",
          "meses_criticos": [],
          "indice": 50,
          "componentes": {"agua": 10.0, "diversidad": 0.0},
          "motivos": [],
          "datos_faltantes": [],
          "riesgos": [],
          "provisional": true,
          "fuentes": []
        }
      ]
    }
  ]
}
```

`datos/rotaciones.js` es el mismo objeto en `window.__ROTACIONES__`.

## Límites conocidos

- El clima es de **celda de modelo** (POWER), no de la parcela.
- La tabla provisional no sirve para decidir siembras: solo para que la app
  tenga forma mientras llega la tarea 8.
- Sin `datos/fincas.json` (tarea 1), el generador termina con código 2 y no
  escribe nada; no inventa fincas.
