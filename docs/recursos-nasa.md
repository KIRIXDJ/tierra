# Recursos del reto oficial (2026)

Reto: **Field Shift: Adapting Farms with NASA Data**
([detalles](https://www.spaceappschallenge.org/2026/challenges/adapting-farms-with-nasa-data/?tab=details),
[recursos](https://www.spaceappschallenge.org/2026/challenges/adapting-farms-with-nasa-data/?tab=resources)).
Leído el 2026-11-13.

## Lo que el reto exige y dónde está en TIERRA

| Requisito del reto | Dónde se cumple |
|---|---|
| Herramienta de apoyo a la decisión con observaciones NASA + suelo local + cultivos + prioridades del agricultor | Panel **Mi parcela**: POWER/ERA5 (clima), ISRIC (suelo), rotaciones con cultivos, deslizadores de prioridad (agua/diversidad) |
| Comparar **al menos 3 rotaciones, incluida la actual** | Bloque **Rotación: 3 estrategias**: Actual 50, Alternativa 1 76, Alternativa 2 93 (índice orientativo) |
| Para cada una: **por qué, evidencia, beneficios, huecos, riesgos** | Tarjeta desplegada al pulsar cada estrategia; datos reales de `datos/rotaciones.json` |
| Explicar incertidumbre | Método: Sen + Mann-Kendall con **FDR**, bootstrap, p ajustada por autocorrelación, bandas P25–P75 |
| Diferencia **satélite frente a medición en tierra** | Método (plegable): reanálisis, píxel de SMAP/IMERG/MODIS/ECOSTRESS mayor que una parcela |
| Prioridades y restricciones del agricultor | Deslizadores agua/diversidad y **escenario de lluvia** (simulación de sensibilidad, no pronóstico) |
| Recordatorio de que no sustituye al agricultor ni al agrónomo | En pantalla (aviso), en cada rotación ("riesgo a revisar") y en el bot |
| Diseño centrado en el agricultor, usable desde el móvil | Vista móvil del monitor y **bot de Telegram real** |
| Mapas interactivos | Globo 3D (tendencias 1984–2025) + mapa satelital de la finca |

## Datasets que usa hoy la app

| Dataset | Uso | Fuente |
|---|---|---|
| **NASA POWER** (MERRA-2) | tendencia 1984–2025, climatología 1991–2020, lluvia/temperatura/radiación, heladas | NASA |
| **NASA POWER** · riesgos | días ≥ 35 °C, lluvia ≥ 20 mm, días secos, heladas, **humedad de raíz (GWETROOT)** y **evapotranspiración (EVLAND)**, base 1991–2020 vs 2021–2025 | NASA |
| **ERA5** (Open-Meteo) | últimos 30 días, normal 1991–2020 de la misma fuente, humedad superficial 0–7 cm | ESA/ECMWF · **no NASA** |
| **Esri World Imagery** | mapa satelital real de las parcelas | Esri · **no NASA** |
| **ISRIC SoilGrids 2.0** | textura, arcilla, arena, carbono orgánico, pH (0–5 cm) | ISRIC · **no NASA** |
| **MODIS/Terra NDVI 16 días** (GIBS) | imagen oficial recortada sobre la finca y valor aproximado decodificado del color (píxel ~289 m) | NASA |
| **GPM IMERG** (GIBS) | lluvia de la pasada sobre la finca (píxel ~2,3 km); “sin lluvia” si el píxel es transparente | NASA |

## Datasets del reto que están en la hoja de ruta

| Dataset | Resolución | Por qué no está todavía |
|---|---|---|
| **SMAP** | ~9 km | el píxel es miles de veces la parcela demo; requiere Earthdata y armonización. La variable de humedad de suelo sí se cubre con POWER (GWETROOT), marcada como reanálisis |
| **GPM / IMERG** | ~0,1° (10 km) | igual, y la app ya usa lluvia ERA5/POWER |
| **Landsat** | 30 m | NDVI a escala de campo: siguiente paso natural |
| **MODIS / VIIRS** | 250–1000 m | **NDVI ya integrado como imagen y valor aproximado vía GIBS**; VIIRS y series temporales, siguiente paso |
| **GPM / IMERG** | ~0,1° (10 km) | **ya integrado como imagen y valor aproximado vía GIBS**; serie diaria completa, siguiente paso |
| **ECOSTRESS** | ~70 m | ET y temperatura de superficie: requiere Earthdata |
| **SRTM** | 30 m | pendiente/riesgo de erosión: falta descargar el tile de la zona |
| **GRACE / GRACE‑FO** | ~300 km | tendencia de agua subterránea: escala regional, se explica como contexto |
| **GEDI** | ~25 m | biomasa/estructura: no hay bosque en la parcela demo |
| **NLDAS / GLDAS** | ~12 km | proxies de ET y humedad: siguiente integración de series |
| **GAEZ (FAO)** | ~5–10 km | idoneidad agroclimática: no NASA |
| **OpenET** | campo (EE. UU.) | solo EE. UU.; no cubre República Dominicana |
| **Web Soil Survey / SSURGO** | campo (EE. UU.) | solo EE. UU.; se usa ISRIC global |
| **CropScape / CDL, NAIP** | 30 m / 1 m | solo EE. UU. |
| **PRISM** | ~800 m | solo EE. UU. |
| **CoCoRaHS, USGS NWIS** | punto | solo EE. UU. |
| **USDA QuickStats, Market News** | condado | solo EE. UU.; el mercado local queda como hueco declarado |
| **Sentinel‑2** | 10–20 m | opción ESA para NDVI fino; pendiente |

## Lo que la app dice en pantalla

- Los sensores, el techo y la cámara son **simulados**; el mapa, el clima, el
  satélite NASA (NDVI/IMERG) y el bot son reales.
- El NDVI/IMERG se muestran como **imagen oficial de GIBS y valor aproximado
  decodificado del color**, no como medición calibrada en la parcela; la app lo
  escribe en pantalla.
- El índice de rotación es **orientativo**, no una recomendación agronómica.
- Falta validación con **agrónomo y parcelas reales**; los parámetros de cultivo
  están marcados como provisionales.
