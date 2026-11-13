# Bot de Telegram de Elio

Bot real de TIERRA (NASA Space Apps 2026). Corre en la laptop, habla con
Telegram por long polling y escribe el estado de los actuadores para que la vista
**Mi parcela** de la app web lo lea por HTTP. El bot se llama **Elio**
(@climaxeliobot).

## Cómo arrancarlo

```bash
cd ~/Documentos/Proyectos/tierra
python3 tools/bot_elio.py
```

Deja el proceso corriendo y habla con el bot desde Telegram (`/ayuda`). Para
pararlo, `Ctrl+C` en esa terminal: **no dejes dos procesos de polling con el
mismo token** (Telegram reparte los updates entre ambos y el agricultor ve
respuestas a medias).

Antes de arrancar, comprueba que el token responde:

```bash
python3 tools/bot_elio.py --ping     # imprime: ping ok · @climaxeliobot
```

El token vive en `.env` (ignorado por git) con el nombre `TELEGRAM_TOKEN`; la
clave de la IA, `DEEPSEEK_API_KEY`. Si faltan, el bot avisa con una frase; nunca
imprime el token ni lo escribe en los datos.

## Comandos

| Comando | Qué hace |
|---|---|
| `/estado [parcela]` | Actuadores, humedad y temperatura de la parcela |
| `/parcelas` | Lista de parcelas con id, cultivo y hectáreas |
| `/clima [parcela]` | Lluvia, temperatura y humedad de los últimos 30 días (ERA5/Open-Meteo) |
| `/rotaciones [parcela]` | Meses secos y las tres estrategias de rotación |
| `/riesgos [parcela]` | Calor ≥ 35 °C, lluvia ≥ 20 mm, días secos, heladas, suelo de raíz y ET (NASA POWER) |
| `/riego on\|off\|auto [parcela]` | Abre o cierra el riego; `auto` quita el override |
| `/techo on\|off\|auto [parcela]` | Cierra o abre el techo; `auto` quita el override |
| `/ventilar on\|off [parcela]` | Abre o cierra la ventilación |
| `/foto [parcela]` | Recorte satelital real del polígono (Esri World Imagery) |
| `/ayuda` | La lista de comandos |

`parcela` acepta el **id** o el **nombre**, con o sin tildes (`la-esperanza`,
`El Hoyo`, `LA LOMA`). Sin argumento usa la primera parcela; `todas` aplica a
las tres.

## Dos modos

- **Modo comandos**: lo de arriba. Cada comando que cambia un actuador
  reescribe `datos/estado_finca.json` (tmp + rename, escritura atómica) y anota
  el intercambio en `ultimo` e `historial` (máximo 20).
- **Modo API**: cualquier texto libre, o `/ia <pregunta>`, va a DeepSeek
  (`deepseek-chat`, temperatura 0.2, 300 tokens) con el contexto estructurado de
  `datos/*.json` y el contrato de Elio: responde solo con ese contexto, en
  español, máximo 3 frases, cita la fuente y si el dato no está dice exactamente
  «No tengo ese dato.». No inventa cifras ni URLs.

Si falta `DEEPSEEK_API_KEY`, el modo API contesta con una frase humana y el bot
sigue funcionando en modo comandos.

## El archivo que lee la app

`datos/estado_finca.json` (no se commitea):

```json
{"version":1,"origen":"telegram","actualizado":"ISO-8601 con zona",
 "modo":"comandos|api",
 "parcelas":{"la-esperanza":{"riego":false,"techo":true,"ventilacion":false}},
 "ultimo":{"texto":"/techo on","respuesta":"Techo cerrado en La Esperanza.","ts":"..."},
 "historial":[{"texto":"...","respuesta":"...","ts":"..."}]}
```

La app lo pide por HTTP cada ~3 s y aplica `riego`, `techo` y `ventilacion`.
Si el archivo no existe, la app sigue en modo simulado. `auto` deja el actuador
en `false` y su mensaje lo dice: es la forma de devolverle el control a la
simulación.

La app marca el bot como «conectado» si `actualizado` es de hace menos de 3
minutos (así distingue un bot vivo de un archivo viejo). Por eso el bot, mientras
escucha, **late cada 60 s**: reescribe `actualizado` sin tocar `ultimo` ni el
historial.

Prueba la integración sin red y sin arrancar el polling:

```bash
python3 tools/bot_elio.py --simular "/techo on"
cat datos/estado_finca.json
```

## Qué es real y qué es simulado

| Pieza | Realidad |
|---|---|
| Clima (POWER, ERA5/Open-Meteo) | **Real**: reanálisis y modelo, etiquetado «no NASA» cuando toca |
| Suelo (ISRIC SoilGrids) | **Real**: no es NASA |
| Mapa satelital | **Real**: Esri World Imagery |
| Parcelas, sensores ESP32, humedad | **Simulados** (son la demo de producto) |
| Riego, techo y ventilación | **Simulados**: el bot solo escribe el estado; no hay hardware |
| Bot de Telegram | **Real** (token de BotFather, long polling) |

## Pruebas

```bash
python3 -m py_compile tools/bot_elio.py
python3 -m unittest tests.test_bot_elio -v   # sin red: HTTP falso inyectado
python3 tools/bot_elio.py --autoprueba       # imprime OK
```

La IA y Telegram son inyectables (`cliente=`), así que las pruebas no tocan la
red. `--ping` es la única prueba que necesita internet.

## Seguridad

- **El token se compartió por chat**, así que conviene **rotarlo**: en
  @BotFather, `/revoke` (o `/token`) y copiar el nuevo a `.env`. Rota también
  `DEEPSEEK_API_KEY` si pasó por un chat.
- El token vive **solo** en `.env`, que está en `.gitignore`. Nunca en código,
  tests, documentación, `datos/` ni en el navegador.
- El bot no imprime el token: `--ping` muestra solo el username y `ok`; los
  errores de red se resumen en una frase sin la URL.

## Límites conocidos

- Un proceso de polling por token; no hay webhook ni servidor público.
- El latido solo mantiene fresca la marca de tiempo: no simula que hay hardware.
- El estado es un único archivo JSON: sirve para una finca de demo, no para
  varias explotaciones a la vez.
- `/foto` recorta el mapa local con la escala de `parcelas.json` (1,1299 m/px);
  no pide una imagen nueva a ningún servicio.
