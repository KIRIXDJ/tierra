# Modelo Canvas de TIERRA

Llenado con el modelo de la profesora **Liddy Kiaty Figueroa** (UNIROMANA):
nueve bloques, sin inventar cifras. Todo lo que no está validado con clientes
lleva **por validar** y las cifras de mercado no se afirman.

> Estado: producto funcional (app, datos NASA, bot real) y **sin clientes
> todavía**. El Canvas sirve para ordenar el negocio, no para fingir tracción.

## 1 · Segmentos de clientes

- **Cooperativas y asociaciones de productores** de hortalizas, tubérculos y
  granos en República Dominicana: deciden la rotación en grupo y comparten
  técnico. *Primer piloto: 3–5 fincas.*
- **Pequeños y medianos productores** con smartphone y acceso a datos móviles;
  hoy deciden con memoria y consejo informal.
- **Agrónomos y técnicos de campo** que asesoran a varios productores: usan la
  herramienta para llevar evidencia a la visita.
- **Agroindustria y exportadores** que piden trazabilidad climática de sus
  proveedores. *Por validar.*
- **ONG y proyectos de desarrollo rural** con programas de agricultura
  climáticamente inteligente. *Por validar.*

## 2 · Propuesta de valor

**“Decide la próxima siembra con 42 años de datos NASA y los datos de tu propia
finca, sin ser experto en satélites.”**

- Un panel que abre en la finca: mapa satelital con las parcelas, sensores,
  clima real, NDVI/IMERG y riesgos (calor, lluvia intensa, secos, heladas,
  suelo de raíz y evapotranspiración).
- **Tres rotaciones comparadas** —la actual y dos alternativas— con porqué,
  evidencia NASA, beneficios, datos que faltan y riesgos a revisar.
- **La incertidumbre a la vista**: FDR, intervalo de confianza y bandas
  normales; cuando falta un dato, la app lo dice.
- **Se usa desde el móvil** y el bot real de Telegram mueve los actuadores.
- **Funciona sin internet** en la feria (datos y satélite van en el repo).

Diferencial frente a una app de riego: no vende solo hardware; traduce datos
públicos de NASA en una decisión agrícola, con límites declarados.

## 3 · Canales

- Web (app estática, se puede publicar en GitHub Pages) y móvil.
- **Bot de Telegram** (@climaxeliobot) como canal de uso diario.
- Talleres y visitas con cooperativas y agrónomos (canal de confianza).
- Repositorio público y NASA Space Apps como escaparate inicial.

## 4 · Relación con clientes

- Acompañamiento en la **primera temporada** (configuración de parcelas y
  prioridades).
- Soporte humano + bot; ayuda en pantalla y en el chat.
- Comunidad de productores y agrónomos que validan las recomendaciones.
- Transparencia: la app repite que **no sustituye** al agricultor ni al agrónomo.

## 5 · Fuentes de ingresos *(por validar)*

- Suscripción por finca/mes (precio **por validar** con 3–5 pilotos).
- Licencia anual a cooperativas o agroindustria por varios productores.
- Instalación y mantenimiento del kit de sensores ESP32.
- Formación y acompañamiento agronómico.

No se afirma TAM, cuota ni ingreso hasta tener pilotos y precio validado.

## 6 · Recursos clave

- Datos: NASA POWER (1984–2025), ERA5/Open-Meteo, ISRIC, NASA GIBS (NDVI e
  IMERG).
- Motor de análisis: Sen + Mann-Kendall con FDR, bootstrap, bandas normales.
- App sin librerías de terceros (three.js y texturas en el repo) y bot real.
- Equipo de 6 (ver deck) y red de agrónomos por construir.
- Reputación: método y límites escritos, código abierto.

## 7 · Actividades clave

- Mantener y validar los datos (snapshots y regeneración).
- Generar recomendaciones con evidencia, huecos y riesgos.
- Instalar y probar sensores en campo.
- Validación agronómica de parámetros de cultivo.
- Soporte a productores y formación de técnicos.

## 8 · Asociaciones clave

- **UNIROMANA** (universidad) y el Club de Tecnología.
- Cooperativas y asociaciones de productores de Constanza, Azua y San Francisco
  de Macorís.
- **Agrónomos locales** (validación) y proveedores de hardware ESP32.
- Comunidad NASA Space Apps y programas de datos abiertos.

## 9 · Costes de estructura

- Desarrollo y mantenimiento (tiempo del equipo).
- Datos y hosting: bajo, la app es estática y los datos van en el repo.
- Hardware piloto: sensores, válvulas y techo motorizado.
- Validación agronómica y visitas de campo (el coste mayor de la fase piloto).
- Soporte y formación.

## Impacto esperado *(a medir con pilotos)*

- Agua ahorrada por riego ajustado a la humedad y la lluvia.
- Decisiones de rotación con evidencia, no solo con memoria.
- Trazabilidad climática para cooperativas y agroindustria.
- Métricas concretas (litros, hectáreas, adopción) **por validar** en la
  siguiente fase.
