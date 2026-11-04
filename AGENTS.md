# Reglas para asistentes de IA en este repositorio

Este repo es la copia canónica de TIERRA. Antes de tocar código, respeta:

## Si eres un agente y te asignaron una tarea

Lee [`tareas/README.md`](tareas/README.md) y **solo** el archivo de tu tarea.
No necesitas el contexto de la conversación que la originó.

1. Rama `tarea/N-slug` desde `main` actualizado. Nunca trabajes en `main`.
2. Toca **solo** los archivos de "Permitido tocar" de tu archivo. Si necesitas
   otro, para y abre un issue; no lo toques "de paso".
3. Corre los "Criterios de aceptación" de tu archivo y pega la salida en el PR.
4. Un commit, en español, con el prefijo que indica tu archivo.
5. No reformatees, no renombres archivos, no actualices dependencias, no
   "arregles" otra tarea.
6. Si el contrato no alcanza, abre un issue `Tarea N · duda` y no inventes.
   Si eres QA, reporta el bug; no lo arregles.

| Si te tocó | Lee | Rama | No toques |
|---|---|---|---|
| 1 · Datos | `tareas/01-datos.md` | `tarea/1-datos` | `web/`, `tools/tendencia.py` |
| 2 · Temporada | `tareas/02-temporada.md` | `tarea/2-temporada` | `web/`, `datos/fincas.json` |
| 3 · Interfaz | `tareas/03-ui.md` | `tarea/3-ui` | `tools/`, `datos/`, `tests/` |
| 4 · Rotaciones | `tareas/04-rotaciones.md` | `tarea/4-rotaciones` | `web/`, `datos/` |
| 5 · QA | `tareas/05-qa.md` | `tarea/5-qa` | código de las otras tareas |
| 6 · Demo | `tareas/06-demo.md` | `tarea/6-demo` | todo lo demás |
| 7 · Rotaciones UI | `tareas/07-rotaciones-ui.md` | `tarea/7-rotaciones-ui` | `tools/`, `datos/`, `tests/` |

## Reglas del proyecto

1. **Nada agronómico inventado.** Todo parámetro de cultivo necesita fuente
   citable (FAO, extensión agrícola, literatura). Si no la hay:
   `"estado": "provisional"`, `"fuente": null` y aviso visible en la interfaz.
2. Los puntajes de rotación son **orientativos**, nunca verdades agronómicas.
3. **No inventar endpoints** ni nombres de parámetros de API. Verificar en la
   documentación y dejar el código tolerante a fallos.
4. La demo debe funcionar **sin internet**: datos precalculados en el repo y
   librerías locales. Las llamadas en vivo son opcionales y con respaldo.
5. **Nunca** leer, imprimir ni subir `.env`. Claves solo en variables de
   entorno; jamás dentro del HTML ni del JS del navegador.
6. Marcar siempre lo que **no es NASA** (por ejemplo Open-Meteo/ERA5).
7. Verificar antes de decir "hecho": `python3 -m unittest discover -s tests`,
   `python3 -m py_compile` y `node --check` del JS extraído.
8. Cambios mínimos; no reformatear código ajeno. Un commit por tarea.
9. No presentar esto como monitoreo de parcela: son estimaciones de celda de
   modelos y reanálisis.
10. **Respaldos temporales fuera del repo.** Los bundles, zips o dumps de
    migración se guardan fuera del proyecto y se borran en cuanto el cambio
    queda confirmado. Nunca se commitean ni se dejan crecer en `/tmp`.

## Respaldo pendiente de borrar

- `/tmp/laboratorio-tierra-20261102.bundle` — **127 MB**. Respaldo de la rama
  privada `feat/tierra-trend-detective`, que se borró el 2026-11-02 al pasar el
  proyecto al repo público. Ya no hace falta ahora que el repo público está
  verificado (32 commits, pruebas en verde, CI en verde):

  ```bash
  rm -f /tmp/laboratorio-tierra-20261102.bundle
  ```

  Si se vuelve a necesitar un respaldo así, que sea temporal y con fecha de
  borrado anotada aquí mismo.

