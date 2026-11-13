# Demo · NASA Space Apps 2026

Guion de 3 minutos, checklist de feria y diapositiva de visión.
**Antes de ensayar**, confirma que la app en `main` hace todo lo que dice aquí.

## Guion (3 minutos)

**0:00–0:30 · El problema**
"Casi la mitad de una finca se decide con el clima del año pasado. Los datos
satelitales existen, pero llegan como capas que el agricultor no puede usar.
Nosotros los convertimos en tres decisiones: cómo viene la temporada, qué
rotación conviene y por qué."

**0:30–1:30 · El globo: 42 años de tendencia**
- Girar el globo, abrir "Caribe", clic en República Dominicana.
- Señalar que el panel ofrece **las fincas de esa celda**: del dato global a la
  finca concreta en un clic.
- Leer: pendiente en °C/década, p-valor y el filtro de significativas.
- Decir: "esto es NASA POWER, que es **reanálisis**, no una medición en la finca."
- Señalar el FDR: "con 2.592 celdas, sin corrección, ~130 por variable saldrían
  significativas por azar; por eso corregimos."

**1:30–2:30 · Esta temporada (30 días)**
- Abrir **Finca**, elegir Constanza.
- Leer la lluvia de 30 días contra la banda normal P25–P75 y la temperatura.
- **Cambiar a Azua** (dato del 13-nov: 178 mm en 30 días frente a una normal de
  88 mm, +103 %). Ese contraste entre dos fincas del mismo país es lo que un
  agricultor necesita ver y la prensa entiende en un segundo.
- Mostrar el suelo (ISRIC SoilGrids) y el enlace "Ver esta celda en el globo":
  conecta la finca con 42 años de tendencia NASA.
- Señalar el pie: fuente **Open-Meteo, no NASA**, con fecha y hora.
- Decir: "esto es una estimación de celda de modelo, no un sensor en tu parcela.
  Por eso va la fecha, y por eso no lo mezclamos con la tendencia de 40 años."

**2:30–3:00 · Rotaciones y cierre**
- Abrir **Rotaciones**: arriba hay una **tabla de comparación** de los tres
  planes (índice, demanda, meses secos que toca, si es provisional). Es la
  comparación que pide el desafío, en una mirada.
- Cada tarjeta añade la **evidencia NASA** (los meses secos de la finca) y la
  coincidencia con los meses en que el plan necesita agua.
- Mover el deslizador "Ahorrar agua" y el **escenario de sequía** (-40 %): los
  índices bajan y se ve qué plan aguanta peor.
- Mostrar que el orden cambia y que cada tarjeta dice **por qué**, **qué falta** y
  **qué revisar con un agrónomo**.
- Cerrar: "El índice es orientativo. El sistema no reemplaza al agricultor: le da
  preguntas mejores para llevar al agrónomo."

**Cierre opcional · Mi parcela, el panel de monitoreo (90 s)**
- Pulsar **Mi parcela**: el globo **vuela hasta Constanza** y entra al mapa
  satelital real. No es un panel en una esquina: el mapa ocupa la pantalla y las
  tres parcelas (La Esperanza 1,06 ha de yuca, El Hoyo 0,71 ha de frijol, La Loma
  1,44 ha de maíz) están dibujadas encima, con sus sensores ESP32 y su cámara.
- Señalar el **panel de la derecha**: humedad de suelo, temperatura del aire y del
  suelo, batería por sensor, minigráfico de 24 h, y el **clima real** de la finca
  (lluvia de 30 días contra su normal, temperatura media, humedad superficial,
  mañana). Pie de fuente: Open-Meteo/ERA5 (no NASA) + NASA POWER histórico.
- **Fotos**: la miniatura de la izquierda es **satélite real** (Esri) recortada
  sobre el polígono; la de la derecha es la **cámara de la finca, simulada** y lo
  dice al ampliarla. Clic para verlas grandes.
- **Techo**: pulsar `cerrar`. La parcela se cubre con el plástico en el mapa y la
  fila pasa a «cerrado · manual». Probar también con el deslizador de **lluvia**:
  con lluvia el automático cierra el techo y suspende el riego.
- **Registrar otra parcela**: botón, cuatro esquinas sobre el mapa, área calculada.
- **El bot es real**: abrir Telegram en el móvil y escribir a **@climaxeliobot**
  `/estado`, `/techo on`, `/clima`, o una pregunta libre en modo API. El panel
  cambia el chip a «Telegram conectado» y refleja el actuador en segundos.
  (Si no hay red en la feria: el chat simulado de la app hace los mismos comandos.)
- Decirlo en la misma frase: **«la app es real, los datos NASA son reales y el bot
  es real; los sensores y el techo son simulados porque hoy no hay hardware
  instalado»**. Es el plano del servicio, no algo que ya esté en el campo.

**Si sobra tiempo o el jurado pide más:**
- **Abrir la app en el móvil** (misma wifi): los paneles se adaptan. El agricultor
  no lleva un portátil al campo.
- **Botón Método**: responde de un vistazo a "¿esto es válido?" — reanálisis,
  satélite frente a terreno y dónde entra el agrónomo.

Si sobra tiempo y Elio está integrado: preguntar "¿está seco?" y mostrar que
responde con la cifra y su fuente, y que dice "no tengo ese dato" cuando falta.

## Checklist de feria (10 minutos antes)

- [ ] `python3 actualizar_reciente.py` corrido **el mismo día** (si el snapshot
      tiene más de 3 días, la app avisa "datos de hace N días").
- [ ] `python3 generar_rotaciones.py` corrido después.
- [ ] Servidor local arriba: `python3 -m http.server 8000` → `localhost:8000/web/`.
- [ ] Bot arriba (si se va a mostrar Telegram de verdad):
      `python3 tools/bot_elio.py` en otra terminal, y probar `/ping` con el móvil.
- [ ] Globo cargado: si el wifi del lugar falla, three.js y las texturas no
      llegan y no hay globo. **Tener el video de respaldo listo.**
- [ ] Pestañas Finca y Rotaciones abiertas una vez (calienta la caché).
- [ ] Zoom del navegador al 100 %, notificaciones silenciadas, pestañas limpias.
- [ ] Ensayo completo una vez con la red del lugar o con hotspot.
- [ ] Llevar `docs/demo.mp4` copiado **fuera** del repo (USB o escritorio): si el
      portátil no abre el navegador, el video salva la presentación.
- [ ] **Probarlo en un móvil** (o en el modo móvil del navegador): el panel debe
      entrar entero y los botones tocarse con el dedo.
- [ ] Servir con `python3 -m http.server`: abrir el archivo con doble clic
      (`file://`) no funciona y la app lo avisa.
- [ ] Cronómetro: el guion no pasa de 3:10.

## Plan B

- **Video ya grabado**: [`demo.mp4`](demo.mp4) — 52 s, 1280×720, 810 KB. Recorre
  globo, temporada, rotaciones, escenario, parcela con sensores, método y Elio.
  Se regenera con `python3 tools/grabar_demo.py` si la app cambia.
- Capturas fijas en [`capturas/`](capturas/) por si el navegador falla.
- Si no hay red: reproducir el video y explicar con las capturas. No fingir que
  la app está corriendo.

## Diapositiva de visión (texto para pegar)

> **De la estimación al campo**
> Hoy: datos NASA + modelo abierto = decisiones con incertidumbre declarada.
> Mañana: sensores de bajo costo (ESP32) en la finca, riego y techo automáticos,
> y Elio por Telegram respondiendo con datos de la propia parcela.
> **Estado: visión, no construido.** Lo que sí existe hoy es la capa de datos,
> la temporada y las rotaciones.

## Reparto del día

| Quién | Hace |
|---|---|
| 1 | Habla (0:00–3:00) |
| 2 | Maneja el ratón y las pestañas |
| 3 | Responde preguntas técnicas (datos, FDR, fuentes) |
| 4 | Vigila el reloj y el plan B (video listo) |

## Lo que no se promete

- No se dice "tiempo real" ni "monitoreo de tu parcela".
- No se presenta la diapositiva de visión como si existiera.
- No se dan cifras que no estén en la app.
- No se menciona Elio si no está en `main` ese día.
