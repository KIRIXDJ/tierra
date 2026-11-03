# Tarea 6 · Demo, pitch y diapositiva de visión

**Entrega:** `docs/demo.md` con el guion de 3 minutos, el checklist offline y el
texto de la diapositiva de visión. **≈3 h.** Depende de que la tarea 3 esté
integrada (o de una captura del estado actual).

**Rama:** `tarea/6-demo` · **Commit:** `docs(demo): guion, checklist offline y visión`

## Permitido tocar

- `docs/demo.md` (nuevo)

## Prohibido

Todo lo demás. Si la demo necesita un arreglo, es un issue para la tarea 3.

## Qué debe contener

1. **Guion de 3 minutos** (minuto a minuto):
   - 0:00–0:30 problema: la finca decide con clima que cambia y datos que no son de su parcela;
   - 0:30–1:30 globo: tendencias 1984–2025 con FDR, una celda del Caribe, aviso de reanálisis;
   - 1:30–2:30 pestaña Finca: "Esta temporada" con los 30 días, la banda normal,
     el pronóstico y la fuente fechada;
   - 2:30–3:00 límites: no es monitoreo de parcela, se valida con agrónomo, Elio no controla nada.
2. **Checklist offline** (marcar antes de salir a la feria):
   - `datos/reciente.js` presente y con fecha reciente;
   - globo y texturas cargan sin red (anotar si siguen en CDN: es deuda conocida);
   - POWER/GIBS/EONET caídos no rompen nada;
   - navegador y pestañas ya abiertas; zoom al 100 %; notificaciones apagadas;
   - ensayo completo una vez sin internet.
3. **Diapositiva de visión** (texto listo para pegar): sensores ESP32 en la finca,
   riego y techo automáticos, asistente por Telegram, **hoy es visión, no está
   construido**; Elio responde solo con los datos de la herramienta y no controla
   actuadores en esta fase.
4. **Reparto del día**: quién habla, quién maneja el ratón, quién responde
   preguntas, quién vigila el reloj.
5. **Plan B**: video de 2 minutos pregrabado y capturas fijas, por si falla la red
   o el proyector.

## Criterios de aceptación

- El guion se lee en voz alta en menos de 3:10.
- Alguien que no conoce el proyecto puede seguirlo sin leer código.
- No promete nada que la app no haga hoy.
- El checklist se puede ejecutar en 10 minutos.

## Trampas

- No digas "tiempo real" para datos de hace un día o de un modelo.
- No presentes la diapositiva de visión como si existiera.
- No metas cifras nuevas que no estén en la app.
