# TIERRA · resumen para el jurado

## El problema

Un agricultor decide qué sembrar y cuándo con el clima del año pasado y con la
memoria de la finca. Los datos satelitales existen, pero llegan como capas
globales que no responden a su pregunta: *¿cómo viene esta temporada y qué
rotación me conviene?*

## Qué construimos

Una herramienta de apoyo a la decisión con tres lentes, los riesgos y una recomendación:

1. **Lente NASA de largo plazo (1984–2025).** Globo con una malla de 2.592
   celdas de 5°: tendencia de Sen y p de Mann-Kendall para temperatura, lluvia,
   viento y humedad. Corregido por pruebas múltiples (**FDR**), con intervalo de
   confianza por bootstrap y p ajustada por autocorrelación.
2. **Lente de la temporada (30 días).** Lluvia, temperatura y humedad superficial
   frente a la banda normal P25–P75 calculada con la **misma fuente**
   (Open-Meteo/ERA5, rotulada como no NASA), más pronóstico de 7 días.
3. **Satélite NASA.** NDVI de MODIS/Terra (16 días) e IMERG de GPM sobre la finca,
   con su fecha y su píxel (289 m y ~2,3 km): se ve la diferencia entre satélite y
   suelo que pide el reto.
4. **Riesgos.** Días de calor extremo, lluvia intensa, días secos, heladas,
   humedad de raíz y evapotranspiración con NASA POWER (MERRA-2), comparados
   contra la base 1991–2020.
5. **Rotaciones.** Tres estrategias —incluida la actual— con índice orientativo,
   **evidencia NASA** (los meses secos de esa finca), motivos, beneficios, datos
   que faltan y riesgos a validar. Deslizadores de prioridades (agua/diversidad) y
   un escenario de sequía para ver qué plan aguanta peor.

Y **Elio**, el bot real de Telegram: responde solo con lo que hay en los datos,
cita la fuente de cada cifra y dice «no tengo ese dato» cuando falta. El bot mueve
los actuadores *simulados* del panel; no hay hardware conectado.

## Qué datos NASA usa, y para qué

| Dato | Fuente | Uso |
|---|---|---|
| Temperatura, lluvia, viento, humedad 1984–2025 | NASA POWER (MERRA-2, reanálisis) | tendencias y meses secos |
| Imágenes satelitales 2000 / 2025 | NASA GIBS (MODIS Terra) | comparación visual |
| Incendios y tormentas | NASA EONET | capas de eventos |
| Temporada actual | Open-Meteo / ERA5 (**no NASA**) | anomalía de 30 días |
| Suelo (textura, carbono, pH) | ISRIC SoilGrids (**no NASA**) | contexto de la finca |
| NDVI (MODIS/Terra 16 días) e IMERG (GPM) | NASA GIBS | vegetación y lluvia sobre la finca (valor aproximado por color) |
| Calor, lluvia intensa, secos, heladas, suelo de raíz y ET | NASA POWER (MERRA-2) | riesgos por año, 1991–2025 |

## Qué tiene de distinto

- **No mezclamos fuentes en una anomalía.** Restar una normal de POWER a un dato
  de ERA5 mide el desajuste entre modelos, no el clima: la validación del propio
  repo vio cocientes de 0,36 a 4,78 en una misma finca. La normal se calcula con
  la misma fuente que el dato reciente.
- **La incertidumbre está a la vista**: FDR, IC, banda P25–P75, p ajustada.
- **Cada cifra dice de dónde viene** y cada recomendación dice qué le falta.
- **La app no carga ninguna librería de terceros**: three.js y las texturas están
  en el repo. Solo se piden datos a las APIs.
- **155 pruebas automáticas** (Python + navegador) y **3 comprobaciones de lógica en Node** (incluye móvil y
  el caso con la red caída).

## Lo que el reto pide y aún no cubrimos

Mercado local, ciclo de plagas y el calendario de campo desnudo **no se miden
todavía**. La materia orgánica se **estima** con el carbono de ISRIC (× 1,724) y la
erosión solo tiene la pendiente SRTM como proxy, no un modelo. Se declaran como
huecos, no se rellenan con supuestos.

## Límites, dichos sin rodeos

- POWER y ERA5 son **reanálisis**: modelos, no un pluviómetro en la parcela.
- El índice de rotaciones es **orientativo** y sus pesos son de diseño.
- La tabla de cultivos está **provisional**: falta revisión de un agrónomo local.
- No hay datos de rendimiento, precios ni textura medida en campo.
- El suelo de dos fincas quedó sin dato porque el servidor de ISRIC no respondió.

Por eso la app incluye un panel **Método y límites** y cada tarjeta dice qué
revisar con un agrónomo. No sustituye al agricultor: le da mejores preguntas.

## Cómo verlo en 2 minutos

```bash
git clone https://github.com/KIRIXDJ/tierra.git && cd tierra
python3 -m http.server 8000
# http://localhost:8000/web/
```

La app abre en **Mi parcela**: mapa, sensores, clima, fotos, techo y la
comparación de las tres rotaciones (con evidencia, huecos y riesgos). Escribir al
bot **@climaxeliobot** (`/estado`, `/techo on`, o una pregunta libre). **×** para
volver al globo → Caribe → celda → "Abrir el monitoreo".
