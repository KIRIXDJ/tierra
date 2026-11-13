# Demo · NASA Space Apps 2026

Guion de 3 minutos, checklist de feria y diapositiva de visión.
**Antes de ensayar**, confirma que la app en `main` hace todo lo que dice aquí.
La app abre directamente en **Mi parcela**; el globo queda detrás y se vuelve con
la **×**.

## Guion (3 minutos)

**0:00–0:25 · El problema**
"Casi la mitad de una finca se decide con el clima del año pasado. Los datos
satelitales existen, pero llegan como capas que el agricultor no puede usar.
Nosotros los convertimos en algo que se usa desde el móvil: cómo va la finca,
qué se riega solo, y qué avisa por Telegram."

**0:25–1:40 · Mi parcela: el producto, a pantalla completa**
- La app ya está abierta en **Mi parcela**: mapa satelital real con las tres
  parcelas encima (La Esperanza 1,06 ha de yuca, El Hoyo 0,71 ha de frijol,
  La Loma 1,44 ha de maíz), sus sensores ESP32 y su cámara.
- Panel derecho: **sensores** (humedad de suelo, temperatura, batería, gráfico de
  24 h) y **clima real** de la finca (lluvia de 30 días contra su normal,
  temperatura, humedad superficial, mañana). Pie de fuente: Open-Meteo/ERA5
  (no NASA) + NASA POWER histórico.
- **Automático**: el riego se activa con la humedad bajo el 25 % y el techo se
  cierra con la lluvia real de ERA5. No hay control para "hacer llover".
- **Riesgos (NASA POWER)**: calor ≥ 35 °C, lluvia ≥ 20 mm, días secos, heladas,
  humedad de raíz y evapotranspiración, con la comparación 1991–2020 vs 2021–2025.
- **Fotos**: la de la izquierda es satélite real (Esri) recortada sobre el
  polígono; la de la derecha es la cámara simulada y lo dice al ampliarla.
- **Techo**: pulsar `cerrar` / `abrir`. La parcela se cubre con el plástico en el
  mapa y la fila pasa a «cerrado».
- **Rotación**: la comparación de las tres estrategias está en el propio monitor
  (Actual 50, Alternativa 1 76, Alternativa 2 93; índice orientativo NASA POWER).
- **Método y límites**: plegado al final del panel; responde a "¿esto es válido?"
  sin abrir otra pestaña.

**1:40–2:25 · El bot es real (el móvil en la mano)**
- Abrir Telegram y escribir a **@climaxeliobot**: `/estado`, `/clima`, `/techo on`.
  El chip cambia a «Telegram conectado» y el panel refleja el actuador en segundos.
- Escribir una pregunta libre (modo API): "¿cómo va la temporada en Constanza?".
  Elio responde con las cifras de `datos/` y su fuente.
  (Si no hay red en la feria: el chat simulado de la app hace los mismos comandos.)
- Decirlo en la misma frase: **«la app, los datos NASA y el bot son reales; los
  sensores, el techo y la cámara son simulados porque no hay hardware instalado»**.

**2:25–3:00 · El globo: por qué esto es NASA y no una app de riego**
- **×** para volver al globo, elegir "Caribe", clic en República Dominicana.
- Leer la celda: pendiente en °C/década, p-valor y el filtro de significativas.
  "Esto es NASA POWER: **reanálisis**, no un termómetro en la finca."
- Señalar el FDR: "con 2.592 celdas, sin corrección, ~130 por variable saldrían
  significativas por azar; por eso corregimos."
- El botón **"Abrir el monitoreo"** de la celda conecta las dos caras: el globo
  vuela a Constanza y entra al panel.
- Cerrar: "El índice es orientativo. El sistema no reemplaza al agricultor: le da
  preguntas mejores para llevar al agrónomo."

## Checklist de feria (10 minutos antes)

- [ ] `python3 actualizar_reciente.py` corrido **el mismo día** (si el snapshot
      tiene más de 3 días, la app lo dice).
- [ ] Servidor local arriba: `python3 -m http.server 8000` → `localhost:8000/web/`.
- [ ] Bot arriba (si se va a mostrar Telegram de verdad):
      `python3 tools/bot_elio.py` en otra terminal; probar `/ping` desde el móvil.
- [ ] Globo cargado: si el wifi del lugar falla, three.js y las texturas no
      llegan. **Tener el video de respaldo listo.**
- [ ] Zoom del navegador al 100 %, notificaciones silenciadas, pestañas limpias.
- [ ] Ensayo completo una vez con la red del lugar o con hotspot.
- [ ] Llevar `docs/demo.mp4` copiado **fuera** del repo (USB o escritorio).
- [ ] **Probarlo en un móvil**: mapa arriba y panel debajo, sin desbordes.
- [ ] Cronómetro: el guion no pasa de 3:10.

## Plan B

- **Video ya grabado**: [`demo.mp4`](demo.mp4) — 52 s, 1280×720.
  Se regenera con `python3 tools/grabar_demo.py` si la app cambia.
  (Ojo: el video es de la versión anterior de la vista; actualízalo antes de la
  feria o enseña capturas nuevas.)
- Capturas fijas en [`capturas/`](capturas/) por si el navegador falla.
- Si no hay red: reproducir el video y explicar con las capturas. No fingir que
  la app está corriendo.

## Diapositiva de visión (texto para pegar)

> **De la estimación al campo**
> Hoy: datos NASA + modelo abierto = decisiones con incertidumbre declarada, y un
> panel que se usa desde el teléfono con el bot real.
> Mañana: sensores de bajo costo (ESP32) en la finca, riego y techo automáticos de
> verdad, y Elio respondiendo con datos de la propia parcela.
> **Estado: el panel y el bot existen; el hardware es la siguiente fase.**

## Reparto del día

| Quién | Hace |
|---|---|
| 1 | Habla (0:00–3:00) |
| 2 | Maneja el ratón, las pestañas y el móvil del bot |
| 3 | Responde preguntas técnicas (datos, FDR, fuentes) |
| 4 | Vigila el reloj y el plan B (video listo) |
