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

**Cierre opcional · Granja conectada (30 s)**
- Abrir **Granja conectada**: bajar la humedad y ver cómo se activa el riego;
  subir la lluvia y ver el techo cerrarse y el riego suspenderse.
- Botón "Enviar aviso al móvil": sale el mensaje con hora, como llegaría por Telegram.
- Decirlo en la misma frase: **"esto es una simulación, hoy no hay hardware instalado"**.
  Es el plano del servicio que se vendería, no algo que ya esté en el campo.

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
  globo, temporada, rotaciones, escenario, granja conectada, método y Elio.
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
