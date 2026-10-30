# Herramientas de datos

`web/index.html` es el demo y funciona solo. Estas herramientas regeneran el
bloque `<script id="malla">` que lleva dentro.

## `malla_global.py`

Descarga la serie mensual 1984–2025 de cuatro variables de NASA POWER para una
rejilla de 5°, calcula la pendiente de Sen y la p de Mann-Kendall de cada celda,
cuenta incendios y tormentas de EONET (2016–2025) y escribe el resultado en
`web/index.html`.

```powershell
cd tierra
python tools/malla_global.py --rejilla 5
```

- `--rejilla N` — tamaño de celda en grados (por defecto 5). Debe dividir 180 y 360.
- `--concurrencia N` — peticiones simultáneas a POWER (por defecto 6).
- `--reanudar` — continúa desde `tools/.malla_parcial.json`.
- `--sin-eventos` — omite EONET (sin capa de incendios/tormentas).
- `--verificar` — no descarga nada: imprime el número de celdas y la tendencia
  de la celda de República Dominicana.

Duración típica: 15–25 minutos con 2.592 celdas. El punto de control se guarda
cada 100 celdas, así que una interrupción se retoma con `--reanudar`.

## Variables

| Id | Nombre | Unidad |
|---|---|---|
| `T2M` | Temperatura | °C/década |
| `PRECTOTCORR` | Lluvia | mm/año por década |
| `WS2M` | Viento | m/s por década |
| `RH2M` | Humedad | %/década |

`GWETROOT` (humedad de la raíz) se descartó porque POWER la devuelve como `-999`
sobre el océano.
