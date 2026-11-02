# TIERRA · Detective de Tendencias

Herramienta de apoyo a la decisión para adaptar cultivos con datos de la NASA.
Globo 3D interactivo con tendencias climáticas 1984–2025 y, en desarrollo, una
capa de seguimiento de la temporada actual. Proyecto para **NASA Space Apps
Challenge 2026**.

> Es una herramienta de apoyo: no reemplaza el juicio del agricultor ni de un
> agrónomo local.

## Qué hace

- Globo 3D con una malla de 2.592 celdas de 5° y la tendencia (Sen) de
  temperatura, lluvia, viento y humedad relativa, con p-valor de Mann-Kendall
  **corregido por FDR** (Benjamini-Hochberg sobre las 2.592 pruebas de cada
  variable).
- Panel por celda: pendiente por década, intervalo de confianza por bootstrap,
  p ajustada por autocorrelación y serie 1984–2025 (en vivo desde NASA POWER
  cuando hay red).
- Contraste de lluvia con Open-Meteo (ERA5) para detectar discrepancias de
  reanálisis, etiquetado como **no NASA**.
- Capas de incendios y tormentas activas (EONET) y comparación satelital (GIBS).
- En desarrollo: capa agrícola (fincas, rotaciones) y tarjeta "Esta temporada"
  con los últimos 30 días y el pronóstico de 7.

## Cómo abrirlo

Sin instalar nada. Dos formas:

```bash
# opción 1: servidor local (recomendado)
python3 -m http.server 8000
# abrir http://localhost:8000/web/

# opción 2: abrir web/index.html directamente en el navegador
```

Necesita un navegador con WebGL 2 (Chrome, Edge o Firefox recientes).
**Sin internet** el globo y la malla funcionan; las capas en vivo (POWER, GIBS,
EONET) y la comparación satelital no.

## Datos y fuentes

| Dato | Fuente | Tipo |
|---|---|---|
| Temperatura, lluvia, viento, humedad 1984–2025 | [NASA POWER](https://power.larc.nasa.gov/) (MERRA-2) | **reanálisis** |
| Imágenes satelitales | NASA GIBS (MODIS Terra) | observación |
| Incendios y tormentas | NASA EONET | eventos |
| Contraste de lluvia | Open-Meteo (ERA5) | **no NASA** |

POWER es reanálisis: no es una medición en tu parcela. La lluvia y el viento de
reanálisis son poco fiables; la app los marca con aviso de confianza baja.
Open-Meteo se acredita en `NOTICE` (CC BY 4.0).

## Estructura

```
web/            app de un solo archivo (index.html) + visor de manos
tools/          malla global, tendencia, cliente de POWER, eventos
tests/          pruebas de la lógica y del demo
textures/       texturas del globo
tierra.py       app de escritorio (pygame) — histórico, no es la demo web
```

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

21 pruebas. `tests/test_demo.py` necesita `playwright` y un Chrome; si no está,
se salta sola. Las demás no necesitan internet.

## Equipo

Reparto de tareas y contratos de datos en [`docs/tareas.md`](docs/tareas.md).

## Límites conocidos

- Todavía hay dependencias por CDN (three.js, MediaPipe, texturas): falta
  localizarlas para que la demo funcione 100 % sin internet.
- La capa agrícola y el asistente Elio están en diseño.
- Los puntajes de rotación serán orientativos y se marcarán como provisionales
  cuando falte una fuente citable.

## Licencia

Código bajo MIT (ver `LICENSE`). Datos y librerías de terceros, ver `NOTICE`.
