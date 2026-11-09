# Graph Report - tierra  (2026-11-09)

## Corpus Check
- 40 files · ~50,713 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 4, .example 1)

## Summary
- 693 nodes · 1403 edges · 35 communities (21 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7fa6c2d3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Pruebas de malla y tendencia
- Pruebas de fincas y POWER
- App de escritorio (globo)
- Validación de lluvia POWER
- Órbitas y astronomía
- Rastreador de satélites
- Pruebas del globo
- Servicio NASA (APOD/NeoWs)
- Temporada y Elio (JS)
- CLI de POWER
- Comparación satelital
- Eventos EONET (pruebas)
- Fincas y rotaciones
- Texturas y nubes
- CI de GitHub Actions
- Temporada: contrato y datos
- Geometría y escena 3D
- Climatología y anomalías
- TLE de Celestrak
- Render del globo
- Estadística del panel (JS)
- Fechas y geometría EONET
- Scripts de escritorio
- Manos y protocolo de tareas
- APOD desde la web
- Cliente EONET
- Geometría de eventos
- Texturas de la Tierra

## God Nodes (most connected - your core abstractions)
1. `Tierra` - 91 edges
2. `Tierra` - 53 edges
3. `RastreadorSatelites` - 23 edges
4. `NasaService` - 21 edges
5. `NasaError` - 18 edges
6. `html_de_prueba()` - 18 edges
7. `TestGlobo` - 15 edges
8. `main()` - 15 edges
9. `ErrorPower` - 14 edges
10. `descargar_celda()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `banda_por_anio() (P25–P75)` --semantically_similar_to--> `intervaloBootstrap()`  [INFERRED] [semantically similar]
  tareas/02-temporada.md → web/index.html
- `Modo demo ?demo (mano sintética)` --conceptually_related_to--> `Tarea 6 · Demo, pitch y visión`  [INFERRED]
  web/manos.html → tareas/06-demo.md
- `Tarea 7 · Pestaña Rotaciones y prioridades` --conceptually_related_to--> `window.__tierra · superficie de prueba`  [INFERRED]
  tareas/07-rotaciones-ui.md → web/index.html
- `main()` --uses--> `ErrorPower`  [INFERRED]
  generar_fincas.py → tools/power_cliente.py
- `TestDescargarMensual` --uses--> `ErrorPower`  [INFERRED]
  tests/test_fincas.py → tools/power_cliente.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Protocolo de ramas y alcance por tarea** — agents_protocolo_tareas, tareas_readme_protocolo, docs_tareas_mapa, docs_tareas_main_protegida, tareas_readme_orden_dependencias [EXTRACTED 1.00]
- **Day/night terminator blend with ocean specular highlight** — textures_earth_day_earthdayalbedomap, textures_earth_night_earthnightlightsmap, textures_earth_specular_earthspecularwatermask [INFERRED 0.85]
- **Flujo de la anomalía de temporada (misma fuente ERA5)** — tareas_00_contratos_regla_oro_fuentes, tareas_00_contratos_reciente_json, tareas_00_contratos_climatologia_era5_json, tareas_02_temporada_reciente, tareas_03_ui_panel_finca, tareas_10_elio_asistente [INFERRED 0.85]
- **Pipeline de tendencias NASA POWER (Sen + Mann-Kendall + FDR)** — readme_reanalisis_power, tools_malla_global, web_index_malla_json, web_index_aplicar_fdr, web_index_pintar_panel, readme_fdr_benjamini_hochberg [INFERRED 0.85]
- **Earth texture set composited by the globe renderer** — textures_earth_day_earthdayalbedomap, textures_earth_night_earthnightlightsmap, textures_earth_specular_earthspecularwatermask, textures_earth_clouds_earthcloudcovermask [INFERRED 0.95]

## Communities (35 total, 14 thin omitted)

### Community 0 - "Pruebas de malla y tendencia"
Cohesion: 0.06
Nodes (24): NASA EONET (incendios y tormentas), Globo 3D interactivo de 2.592 celdas, Pendiente de Sen (tendencia por década), TestHtmlMalla, TestMalla, leer_malla(), reemplazar_malla(), _campos() (+16 more)

### Community 1 - "Pruebas de fincas y POWER"
Cohesion: 0.06
Nodes (24): ahora_local(), construir_finca(), escribir(), generar(), _linea_finca(), main(), _redondear(), resumen_climatologia() (+16 more)

### Community 3 - "Validación de lluvia POWER"
Cohesion: 0.08
Nodes (24): coherencia_x24(), dias_extremos(), ErrorValidacion, _f(), main(), _maximo(), mes_de(), _mm() (+16 more)

### Community 4 - "Órbitas y astronomía"
Cohesion: 0.12
Nodes (12): _ahora_utc(), _eci_a_geografica(), _elementos_actuales(), _estado_kepleriano(), _estado_sgp4(), _gmst(), _julian_date(), _normalizar_instante() (+4 more)

### Community 6 - "Pruebas del globo"
Cohesion: 0.14
Nodes (3): html_de_prueba(), malla_pequena(), TestGlobo

### Community 7 - "Servicio NASA (APOD/NeoWs)"
Cohesion: 0.11
Nodes (8): _fecha_evento(), _fecha_evento_inicio(), _fechas_satelite(), _get(), _get_json(), NasaError, NasaService, _texto()

### Community 9 - "Temporada y Elio (JS)"
Cohesion: 0.18
Nodes (14): textoAnomalia(), evaluar_rotaciones(), generar_rotaciones.py, tools/rotaciones.py (motor puro), Tarea 4 · Motor de rotaciones, Cálculo del índice en el cliente, Deslizadores de prioridades (agua/diversidad), Tarea 7 · Pestaña Rotaciones y prioridades (+6 more)

### Community 10 - "CLI de POWER"
Cohesion: 0.16
Nodes (5): TestMannKendall, TestSen, mann_kendall(), pendiente_decada(), sen()

### Community 12 - "Eventos EONET (pruebas)"
Cohesion: 0.08
Nodes (15): consultar(), ErrorPower, _f(), imprimir(), main(), periodo(), resumir(), _valor() (+7 more)

### Community 13 - "Fincas y rotaciones"
Cohesion: 0.17
Nodes (14): Capa agrícola (fincas y rotaciones), Tarjeta «Esta temporada» (30 d + 7 de pronóstico), NASA GIBS (MODIS Terra), NASA POWER (MERRA-2) · reanálisis, TIERRA · Detective de Tendencias, tierra.py · app de escritorio (pygame), Dependencias Python (requirements.txt), datos/fincas.json (climatología POWER 1991–2020) (+6 more)

### Community 14 - "Texturas y nubes"
Cohesion: 0.31
Nodes (9): datos/reciente.js (espejo window.__RECIENTE__), evaluar_frescura(), cargarReciente(), dibujarSerie30(), Panel #finca (aside de temporada), Tarea 3 · Interfaz «Esta temporada» (pestaña Finca), window.__tierra · superficie de prueba, dibujarSerie() (+1 more)

### Community 15 - "CI de GitHub Actions"
Cohesion: 0.13
Nodes (14): jobs, pruebas, name, on, pull_request, push, runs-on, steps (+6 more)

### Community 16 - "Temporada: contrato y datos"
Cohesion: 0.33
Nodes (11): Open-Meteo (ERA5) · no NASA, datos/climatologia_era5.json (normal 1991–2020), Fixtures de prueba (tests/fixtures), datos/reciente.json (snapshot de 30 días), actualizar() — escritura inyectable, actualizar_reciente.py, Tarea 2 · Seguimiento de la temporada (Open-Meteo), Checklist de revisión de textos (+3 more)

### Community 19 - "Climatología y anomalías"
Cohesion: 0.43
Nodes (7): Protocolo por tarea: rama tarea/N-slug, Calendario 3 nov → 15 nov, main protegida + check CI «pruebas», Mapa de tareas del equipo, Reparto de roles (A–F), Contratos de datos (fijos), Protocolo obligatorio de tareas

### Community 20 - "TLE de Celestrak"
Cohesion: 0.13
Nodes (7): _bloques_tle(), _celestrak_get(), descargar_tles(), _elementos_tle(), _fecha_epoca_tle(), _i(), _registro_tle()

### Community 23 - "Estadística del panel (JS)"
Cohesion: 0.15
Nodes (14): Prueba de Mann-Kendall, Checklist de feria, Guion de 3 minutos, Tarea 6 · Demo, pitch y visión, Diapositiva de visión (ESP32, riego, Telegram), aplicarFDR(), contrasteLluvia(), intervaloBootstrap() (+6 more)

### Community 24 - "Fechas y geometría EONET"
Cohesion: 0.40
Nodes (5): Definiciones de anomalía (ventana, normal, banda), banda_por_anio() (P25–P75), construir_climatologia(), normal_ventana(), tools/reciente.py (lógica pura)

### Community 26 - "Scripts de escritorio"
Cohesion: 0.18
Nodes (6): _descargar_satelite(), _png_satelite(), _rgb_y_cobertura(), SateliteSinCobertura, main(), main()

### Community 27 - "Manos y protocolo de tareas"
Cohesion: 0.32
Nodes (8): Reglas del proyecto para asistentes de IA, Respaldos temporales fuera del repo, Verificar antes de decir «hecho», Límite conocido: dependencias por CDN, Módulo de manos MediaPipe en el globo, gestoDe() (pinza/apuntando/zoom), HandLandmarker (MediaPipe tasks-vision), visor de manos · 21 puntos

### Community 31 - "Geometría de eventos"
Cohesion: 0.20
Nodes (6): _bbox_satelite(), _coord(), _f(), _promedio(), _punto_evento(), _punto_poligono()

### Community 33 - "Texturas de la Tierra"
Cohesion: 0.50
Nodes (5): Cloud mask stored as luminance with no alpha channel, Earth Cloud Cover Mask (single-channel grayscale, white = cloud), Earth Day Albedo Map (2K equirectangular, clouds baked in), Earth Night Lights Map (city lights on black, no political borders), Earth Specular Water Mask (white ocean, black land)

## Knowledge Gaps
- **7 isolated node(s):** `Calendario 3 nov → 15 nov`, `gestoDe() (pinza/apuntando/zoom)`, `Respaldos temporales fuera del repo`, `Verificar antes de decir «hecho»`, `Dependencias Python (requirements.txt)` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 214 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Tierra` connect `Render del globo` to `Rastreador de satélites`, `Servicio NASA (APOD/NeoWs)`, `Eventos y visor del globo`, `Geometría y escena 3D`, `Capas NASA del globo`, `Visor de satélite`, `Panel NASA (APOD)`, `Scripts de escritorio`, `HUD y panel de satélites`?**
  _High betweenness centrality (0.265) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Tierra` (e.g. with `NasaService` and `RastreadorSatelites`) actually correct?**
  _`Tierra` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Calendario 3 nov → 15 nov`, `gestoDe() (pinza/apuntando/zoom)`, `Respaldos temporales fuera del repo` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Pruebas de malla y tendencia` be split into smaller, more focused modules?**
  _Cohesion score 0.06259426847662142 - nodes in this community are weakly interconnected._
- **Why does `Tierra` connect `App de escritorio (globo)` to `Scripts de escritorio`, `Servicio NASA (APOD/NeoWs)`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `NasaService` (e.g. with `Tierra` and `Tierra`) actually correct?**
  _`NasaService` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Pruebas de fincas y POWER` be split into smaller, more focused modules?**
  _Cohesion score 0.05654761904761905 - nodes in this community are weakly interconnected._