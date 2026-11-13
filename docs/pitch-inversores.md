# Pitch para inversores · TIERRA

Guion de 5 minutos, preguntas difíciles y lo que **no** se dice.
La presentación está en [`deck/index.html`](deck/index.html) (11 diapositivas,
teclas ← →, funciona sin internet).

> Contexto: no tenemos acceso a parcelas ni a agrónomos todavía. Por eso el
> discurso separa **lo que ya funciona** de **cómo sería el servicio**. Nunca se
> mezclan: un inversor detecta una promesa disfrazada en 30 segundos.

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
pruebas múltiples), los últimos 30 días contra su propia normal, y tres rotaciones
comparadas con los meses secos de esa finca.
"Esto no es un mockup: se clona, se abre y funciona sin internet."

**4. Producto completo (60 s)**
"Cómo se ve cuando está instalado: sensores ESP32 por parcela, riego que se
dispara solo, techo que se cierra con lluvia y aviso al móvil por Telegram."
Mostrar **Mi parcela**: elegir una parcela registrada y ver su humedad, sus
sensores, su cámara y el riego/techo reaccionando. Decir en la misma frase:
*"esto es una simulación, hoy no hay hardware instalado"*.

**5. Por qué nosotros (45 s)**
"Lo que casi nadie hace: decir qué no sabe. No mezclamos fuentes, corregimos por
pruebas múltiples y el asistente responde «no tengo ese dato» cuando falta.
Eso es lo que un agrónomo puede auditar."

**6. Estado y huecos (30 s)**
"Hecho: app funcionando, 82 pruebas automáticas, repositorio público.
No hecho: validación agronómica, hardware en campo y precio."

**7. El ask (30 s)**
"No pedimos un cheque en blanco. Pedimos **3 a 5 fincas y un agrónomo** para
validar. Con eso medimos ahorro de agua y mejora de decisión, y entonces sí
podemos hablar de inversión con números propios."

## Preguntas difíciles (y respuestas honestas)

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
- [ ] Tener la app abierta en **Mi parcela** y en **Rotaciones**.
- [ ] Decidir quién responde cada bloque de preguntas.
- [ ] Video de respaldo de 2 minutos.
