# Reglas para asistentes de IA en este repositorio

Este repo es la copia canónica de TIERRA. Antes de tocar código, respeta:

## Si eres un agente y te asignaron una tarea

Las tareas del equipo viven en `interno/tareas/` (fuera de git, ver más abajo).
Lee **solo** el archivo de tu tarea. No necesitas el contexto de la conversación
que la originó.

1. Rama `tarea/N-slug` desde `main` actualizado. Nunca trabajes en `main`.
2. Toca **solo** los archivos de "Permitido tocar" de tu archivo.
3. Corre los "Criterios de aceptación" de tu archivo y pega la salida en el PR.
4. Un commit, en español, con el prefijo que indica tu archivo.
5. No reformatees, no renombres archivos, no actualices dependencias, no
   "arregles" otra tarea.
6. Si el contrato no alcanza, pregunta y no inventes.

## Antes de tocar datos o textos

Lee `interno/reto-y-recursos.md` (fuera de git): tiene lo que pide el reto, qué
recursos oficiales usamos, cuáles faltan y qué está declarado como hueco. Si
cambias una cifra o un texto que aparece allí, actualiza esa tabla.

## Reglas del proyecto

1. **Nada agronómico inventado.** Todo parámetro de cultivo necesita fuente
   citable (FAO, extensión agrícola, literatura). Si no la hay:
   `"estado": "provisional"`, `"fuente": null` y aviso visible en la interfaz.
2. Los puntajes de rotación son **orientativos**, nunca verdades agronómicas.
3. **No inventar endpoints** ni nombres de parámetros de API. Verificar en la
   documentación y dejar el código tolerante a fallos.
4. La demo **funciona sin internet**: three.js está en `web/vendor/`, las
   texturas en `textures/` y los datos en `datos/`. Solo las capas en vivo
   (POWER, GIBS, EONET) y el bot piden red. No la conviertas en dependiente de
   un CDN.
5. **Nunca** leer, imprimir ni subir `.env`. Claves solo en variables de
   entorno; jamás dentro del HTML ni del JS del navegador.
6. Marcar siempre lo que **no es NASA** (por ejemplo Open-Meteo/ERA5).
7. Verificar antes de decir "hecho": `python3 -m unittest discover -s tests`,
   `python3 -m py_compile` y `node --check` del JS extraído.
8. Cambios mínimos; no reformatear código ajeno. Un commit por tarea.
9. No presentar esto como monitoreo de parcela: son estimaciones de celda de
   modelos y reanálisis.
10. **Material interno fuera de git.** `interno/` (guion de la demo, Canvas,
    guiones de pitch, reparto de tareas, procesos) está en `.gitignore`: no se
    commitea ni se enlaza desde `README.md` ni desde `docs/`. Lo que se publica
    es el producto, el método y los límites, no la estrategia de presentación.
