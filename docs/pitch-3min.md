# Pitch de 3 minutos · modelo de la profesora

Estructura de **Elevator Pitch** de la Dra. Liddy Kiaty Figueroa (UNIROMANA):
gancho → problema → solución → propuesta de valor → modelo de negocio → impacto
→ llamado a la acción. **3:00 en total**, con la demo ya abierta en el monitor.
El Canvas completo está en [`canvas.md`](canvas.md) y la guía de demo en
[`demo.md`](demo.md).

Demo en vivo para el jurado: **https://kirixdj.github.io/tierra/web/**

## Antes de empezar (10 s, sin hablar)

- App abierta en **Mi parcela** (abre sola), zoom del navegador al 100 %.
- Video de respaldo a mano y bot encendido si hay wifi.
- Cronómetro visible para quien presenta.

## Guion (3:00)

### 1 · Gancho — 0:00–0:15

> "La misma semana, en Azua llovió **el doble** de lo normal y en Constanza lo
> justo. Las dos fincas están en el mismo país. El agricultor decidió con la
> memoria del año pasado."

*Señalar el mapa de la finca en pantalla; no hace falta tocar nada.*

### 2 · Problema — 0:15–0:45

> "Los satélites producen capas globales que no contestan la pregunta del
> agricultor: **¿qué siembro, cuándo riego y qué riesgo tengo en mi finca?**
> Y un agrónomo no puede estar todos los días en todas las parcelas."

- Clic en **Riesgos**: "calor, lluvia intensa, días secos, heladas, suelo y
  evapotranspiración ya están medidos con NASA POWER".
- Frase honesta: "esto es reanálisis, no un sensor en la parcela; por eso lo
  decimos en pantalla".

### 3 · Solución — 0:45–1:25

> "Esto es TIERRA: abre en la finca, no en un mapa del mundo."

- **Mapa**: parcelas, sensores y cámara sobre satélite real.
- **Satélite NASA**: NDVI de MODIS e IMERG de GPM con fecha y tamaño de píxel.
- **Terreno SRTM**: elevación, pendiente y % de pendiente ≥ 15° como proxy de
  erosión; la rotación añade la materia orgánica estimada (carbono × 1,724).
- **Rotación**: "tres estrategias —la actual y dos alternativas— con porqué,
  evidencia, beneficios, lo que falta y el riesgo a revisar".
- Cambiar el **escenario de lluvia** a −40 %: "así se ve cuál aguanta peor".

### 4 · Propuesta de valor — 1:25–1:55

> "La diferencia: **no vendemos solo hardware ni una app de riego**. Traducimos
> 42 años de datos NASA en una decisión agrícola, con la incertidumbre a la
> vista. Y cuando falta un dato, lo dice: 'no tengo ese dato'. Es lo que un
> agrónomo puede auditar."

- Clic en **Método y límites**: FDR sobre 2.592 celdas, intervalo de confianza,
  satélite frente a suelo.
- "Funciona **sin internet**: se clona el repo y abre; ese es el plan B de la
  feria."

### 5 · Modelo de negocio — 1:55–2:15

> "El negocio: suscripción por finca, licencia a cooperativas y la instalación
> del kit de sensores. Los precios están **por validar** con los pilotos; no
> vamos a inventar un mercado."

- Mostrar el Canvas (diapositiva) si hay proyector: 9 bloques, clientes y canales.

### 6 · Impacto — 2:15–2:35

> "El impacto que vamos a medir: agua ahorrada, decisiones con evidencia y
> trazabilidad climática para la cooperativa. Hoy tenemos la herramienta y el
> método; falta medirlo en campo."

- "El bot real mueve los actuadores simulados: el hardware es la siguiente fase,
  y lo decimos en la misma frase."

### 7 · Llamado a la acción — 2:35–3:00

> "No pedimos un cheque en blanco. Pedimos **3 a 5 fincas y un agrónomo** para
> validar esta temporada. Con eso medimos el ahorro y entonces hablamos de
> inversión con números propios. ¿Nos ayudas?"

- Cerrar con la app en pantalla y el bot en la mano; silencio de 2 s.

## Si el jurado pregunta (respuestas cortas)

- **"¿De dónde salen los parámetros de cultivo?"** "De una tabla interna marcada
  como provisional; el ask incluye la validación agronómica."
- **"¿El bot ya funciona?"** "Sí, es real; los actuadores que mueve son simulados
  porque no hay hardware instalado."
- **"¿Qué los hace distintos?"** "Decir qué no sabemos y no mezclar fuentes;
  FDR e incertidumbre a la vista."
- **"¿Mercado?"** "Por validar; primero 3–5 fincas y precio con datos propios."

## Ensayo

- Cronómetro por bloque; si un bloque se pasa, recortar del 2 y del 6.
- Tiempos medidos de las acciones de pantalla: [`ensayo-tiempos.md`](ensayo-tiempos.md)
  (se regeneran con `python3 tools/ensayo_demo.py`).
- Ensayar dos veces sin internet y una con el bot.
- Plan B: si la app falla, `docs/demo.mp4` (46 s) y las capturas de `docs/capturas/`.
