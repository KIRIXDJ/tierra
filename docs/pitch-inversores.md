# Pitch para inversores · TIERRA

Guion de 5 minutos, preguntas difíciles y lo que **no** se dice.
La presentación está en [`deck/index.html`](deck/index.html) (11 diapositivas,
teclas ← →, funciona sin internet).

> Contexto: no tenemos acceso a parcelas ni a agrónomos todavía. Por eso el
> discurso separa **lo que ya funciona** de **cómo sería el servicio**. Nunca se
> mezclan: un inversor detecta una promesa disfrazada en 30 segundos.
>
> Para la expo de 3 minutos con la estructura de elevator pitch (gancho,
> problema, solución, propuesta de valor, modelo, impacto y cierre) usar
> [`pitch-3min.md`](pitch-3min.md); el Canvas del negocio está en
> [`canvas.md`](canvas.md).

## Guion (5 minutos)

**1. Gancho (30 s)**
"Dos fincas en el mismo país, la misma semana. En Azua cayó **el doble** de lluvia
de lo normal para esas fechas; en Constanza, lo justo. Si les das el promedio
nacional, aciertas con una y fallas con la otra."

**2. Problema (45 s)**
"El agricultor decide con la memoria del año pasado. Los satélites producen capas
globales que no contestan su pregunta: *¿cómo viene esta temporada y qué siembro?*"

**3. Lo que ya funciona (60 s)**
Tres lentes sobre la misma finca: 42 años de tendencia NASA (con corrección por
pruebas múltiples), los últimos 30 días contra su propia normal, y **tres rotaciones
comparadas** con su porqué, evidencia, beneficios, huecos y riesgos. Encima, dos
capas reales del reto: **NDVI de MODIS e IMERG de GPM** y **riesgos climáticos de
POWER** (calor, lluvia intensa, secos, heladas, suelo y ET).
"El reto oficial (Field Shift) pide exactamente eso; y esto no es un mockup: se
clona, se abre y funciona sin internet, con el bot real por Telegram."

**4. Producto completo (60 s)**
"Cómo se ve cuando está instalado: sensores ESP32 por parcela, riego que se
dispara solo, ventilación de invernadero, techo que se cierra con lluvia y
control por Telegram desde el móvil."
Pulsar **Mi parcela**: el globo vuela a Constanza y abre el **panel de monitoreo**
a pantalla completa, con el mapa satelital real y las tres parcelas encima.
Mostrar en 40 segundos: lecturas de los sensores, clima real NASA/ERA5, las dos
fotos (satélite real y cámara simulada) y **cerrar el techo** con un clic.
Cerrar con el móvil en la mano: escribir a **@climaxeliobot** `/estado` y
`/techo on` — el panel cambia solo. El bot es real y tiene **dos modos**:
comandos y preguntas libres (Elio responde con los datos y sus fuentes).
Cerrar con la referencia: *"es el mismo camino que el caso de Hiroki Tomiyasu,
el agricultor de brócoli que montó su invernadero automatizado sin saber
programar; nosotros añadimos los datos de la NASA."*
Decir en la misma frase: *"la app, los datos y el bot son reales; los sensores y
el techo son simulados, hoy no hay hardware instalado"*.

**5. Por qué nosotros (45 s)**
"Lo que casi nadie hace: decir qué no sabe. No mezclamos fuentes, corregimos por
pruebas múltiples y el asistente responde «no tengo ese dato» cuando falta.
Eso es lo que un agrónomo puede auditar."

**6. Estado y huecos (30 s)**
"Hecho: app funcionando, 148 pruebas automáticas, repositorio público.
No hecho: validación agronómica, hardware en campo y precio."

**7. El ask (30 s)**
"No pedimos un cheque en blanco. Pedimos **3 a 5 fincas y un agrónomo** para
validar. Con eso medimos ahorro de agua y mejora de decisión, y entonces sí
podemos hablar de inversión con números propios."

## Preguntas difíciles (y respuestas honestas)

**«¿El bot de Telegram ya funciona?»**
"Sí: es un bot real con token propio, corre en el portátil y responde por long
polling. Los actuadores que mueve son simulados: no hay relé ni válvula todavía.
El modo API llama a un modelo con el contexto de los datos y la misma regla que
Elio: si no está en los datos, «no tengo ese dato»."

**«¿De dónde salen los parámetros de los cultivos?»**
"De una tabla interna marcada como provisional. No tenemos agrónomo todavía y no
vamos a inventar cifras. Por eso el ask incluye la validación."

**«¿Qué evita que esto lo copie cualquiera?»**
"Hoy, nada: es código abierto y los datos son públicos. La ventaja es la
instalación y el acompañamiento local, y la validación agronómica que hay que
hacer igual. Si eso no resulta defendible, lo diremos."

**«¿Cuánto cuesta el kit y cuánto puede pagar una finca?»**
"No lo sabemos todavía. Es lo primero que mediremos en el piloto; dar un precio
hoy sería inventarlo."

**«¿Cuál es el mercado?»**
"No tenemos una cifra con fuente. Sabemos el perfil que sufre el problema
(pequeña y mediana finca tropical con estación seca) y que el primer paso es
contarlo con datos, no estimarlo con una diapositiva."

**«¿Por qué confiar en vuestros datos?»**
"Porque enseñamos el método y los límites en el propio producto: FDR, intervalo
de confianza, banda normal de la misma fuente y una lista explícita de lo que
falta."

**«¿Esto reemplaza al agrónomo?»**
"No. Le lleva mejores preguntas y le quita trabajo repetitivo de vigilancia."

## Lo que no se dice

- Cifras de mercado, TAM o crecimiento sin fuente.
- Ahorros de agua o aumentos de cosecha que no hemos medido.
- Que el hardware está instalado: es una simulación.
- «Tiempo real» cuando el dato es de ayer o de un modelo.
- Que somos una empresa: somos un equipo con un producto que funciona y una
  hipótesis de negocio por validar.

## Antes de la conferencia (checklist)

- [ ] Completar nombres y roles del equipo (diapositiva 10).
- [ ] Ensayar con cronómetro: no pasar de 5:00.
- [ ] Probar el deck y la app **sin internet** en el portátil que se va a usar.
- [ ] Tener la app abierta en **Mi parcela**, con el chat del bot a la vista y la
      comparación de rotaciones lista para bajar el panel.
- [ ] Decidir quién responde cada bloque de preguntas.
- [ ] Video de respaldo de 2 minutos.
