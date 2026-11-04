# Tareas del equipo

Este archivo es el mapa para personas. Las **instrucciones ejecutables** de cada
tarea están en [`tareas/`](../tareas/README.md): si un colaborador (o su agente)
dice "me tocó la tarea 2", debe leer `tareas/02-temporada.md` y trabajar solo
dentro de su alcance.

## Cambio de regla (base de la demo)

- El producto es **monitoreo en línea**: globo, capas y datos recientes usan
  internet.
- Los datos de tendencia van precalculados en el repo (arranque rápido y respaldo
  si una API falla). La capa "Esta temporada" se guarda en caché: si falla la red,
  se muestra el último dato con su fecha y la etiqueta "sin conexión".
- Los datos de meses o años **solo** sirven para tendencia y estimación, no para
  la cosecha en curso. Por eso la capa nueva trabaja con 30 días + 7 de pronóstico.

## Reparto

| # | Bloque | Archivo de la tarea | Rama | Entregable |
|---|---|---|---|---|
| 1 | Datos y climatología | [`tareas/01-datos.md`](../tareas/01-datos.md) | `tarea/1-datos` | `generar_fincas.py`, `datos/fincas.json` |
| 2 | Temporada | [`tareas/02-temporada.md`](../tareas/02-temporada.md) | `tarea/2-temporada` | `tools/reciente.py`, `actualizar_reciente.py`, `datos/reciente.json`/`.js` |
| 3 | Interfaz | [`tareas/03-ui.md`](../tareas/03-ui.md) | `tarea/3-ui` | chip y panel "Esta temporada" en `web/index.html` |
| 4 | Rotaciones | [`tareas/04-rotaciones.md`](../tareas/04-rotaciones.md) | `tarea/4-rotaciones` | `tools/rotaciones.py` + fuentes |
| 5 | QA | [`tareas/05-qa.md`](../tareas/05-qa.md) | `tarea/5-qa` | `tests/test_reciente_casos.py` + revisión de textos |
| 6 | Demo | [`tareas/06-demo.md`](../tareas/06-demo.md) | `tarea/6-demo` | guion de 3 min, checklist offline, visión |
| 7 | Rotaciones UI | [`tareas/07-rotaciones-ui.md`](../tareas/07-rotaciones-ui.md) | `tarea/7-rotaciones-ui` | pestaña con 3 estrategias y prioridades |
| 8 | Cultivos | [`tareas/08-cultivos.md`](../tareas/08-cultivos.md) | `tarea/8-cultivos` | `datos/cultivos.json` con fuentes |
| 10 | Elio local | [`tareas/10-elio.md`](../tareas/10-elio.md) | `tarea/10-elio` | respuestas deterministas, sin IA |

Los contratos de datos (JSON exactos, reglas y definiciones de anomalía) están
**solo** en [`tareas/00-contratos.md`](../tareas/00-contratos.md). Si cambian,
se cambia ese archivo y se avisa al grupo en el mismo PR.

## Quién hace qué

| Rol | Persona | Tarea |
|---|---|---|
| A · Datos | Ruben · `myticalruben` (invitación pendiente) | 1 |
| B · Temporada | `dnffa151` | 2 |
| C · Interfaz | Oscar · `lafortuna8501-sudo` | 3 y 7 (mismo archivo) |
| D · Agronomía | Marlon · `MarlonRD` | 4 |
| E · QA | Alison · `alisonrodriguez767-maker` | 5 |
| F · Demo | sin asignar | 6 |
| — | pendiente | 8 y 10 |

QA (5) debe hacerlo alguien distinto de quien escribe la 2.

## Calendario (3 nov → 14 nov)

| Fecha | Qué |
|---|---|
| 3 nov | Contratos cerrados, fixture de ejemplo, ramas creadas |
| 4–5 nov | 1 y 2 producen datos; 3 maqueta con el fixture; 4 investiga fuentes |
| 6–7 nov | Integración 2+3; 4 motor; 5 pruebas |
| 8–9 nov | Textos, pulido y dependencias del CDN si da tiempo |
| 10–11 nov | Elio si hay tiempo; 6 prepara demo |
| 12–13 nov | Ensayo con la red del lugar, capturas, video de respaldo |
| 14–15 nov | Evento y entrega |

## Reglas de trabajo en grupo

- Una rama por tarea (`tarea/N-slug`), PR a `main`, CI verde, una revisión.
  `main` está **protegida**: el push directo se rechaza; hacen falta PR y
  que el check `pruebas` pase. El admin puede saltárselo si urge.
- Commits en español, un commit por tarea, con el prefijo del archivo de la tarea.
- No se toca el alcance de otra tarea; si hace falta, issue y aviso.
- Si alguien se bloquea más de 30 min, lo dice; no se queda callado.
- Reunión diaria de 15 min: qué hice, qué sigue, qué me bloquea.

## Pendiente

- Elio (asistente): diseño listo, sin código. Responde solo con el contexto
  estructurado que la app le entrega, cita fuente y no controla actuadores.
- Tarea A completa: catálogo de cultivos con fuente citable y las pantallas de
  comparación de las 3 rotaciones.
- Localizar three.js, texturas y MediaPipe: sin red la app no arranca (no es
  "modo offline", es no depender de un CDN para pintar).
