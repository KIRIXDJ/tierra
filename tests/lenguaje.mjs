/* Prueba del lenguaje de campo (Node, sin navegador). */
import assert from 'node:assert/strict';
import * as L from '../web/lenguaje.js';

// Lluvia: 1 mm = 1 litro por m², redondeado para leer de lejos.
assert.equal(L.lluvia(126.8), '127 L por m²');
assert.equal(L.lluvia(0), '0 L por m²');
assert.equal(L.lluvia(null), 'sin dato');

// Comparación contra su normal.
assert.equal(L.comparacionLluvia(3), '+3 % sobre su normal');
assert.equal(L.comparacionLluvia(-12), '-12 % sobre su normal');
assert.equal(L.comparacionLluvia(0), 'igual que su normal');
assert.equal(L.comparacionLluvia(undefined), 'sin normal');

// Lluvia por hora: cero se dice con palabras, no con 0,0 mm/h.
assert.equal(L.lluviaHora(0), 'no está lloviendo');
assert.equal(L.lluviaHora(0.04), 'no está lloviendo');
assert.equal(L.lluviaHora(1.2), 'cae 1,2 L por m² por hora');

// Verde: NDVI 0–1 en puntos de 100.
assert.equal(L.verde(0.65), 'verde 65 de 100');
assert.equal(L.verde(0), 'verde 0 de 100');
assert.equal(L.verde(undefined), 'sin dato');

// Agua que gasta el cultivo al día.
assert.equal(L.aguaQueGasta(2.38), 'el cultivo gasta 2,4 L por m² al día');

// Estado de humedad con el mismo umbral que usa el riego automático.
assert.equal(L.estadoHumedad(18), 'seco · hay que regar');
assert.equal(L.estadoHumedad(33), 'regular');
assert.equal(L.estadoHumedad(45), 'con agua');
assert.equal(L.estadoHumedad(null), 'sin lectura');

// Días secos, puntaje y hectáreas.
assert.equal(L.diasSecos(215.6), '216 días sin lluvia al año');
assert.equal(L.puntaje(93), 'puntaje 93/100');
assert.equal(L.superficieHa(1.27), '1,27 ha · 12.700 m²');
assert.equal(L.areaM2(1.27), '12.700 m²');

// Pendiente en palabras; los grados quedan entre paréntesis.
assert.equal(L.pendiente(3.5), 'casi plano (3,5°)');
assert.equal(L.pendiente(9), 'algo inclinado (9,0°)');
assert.equal(L.pendiente(20), 'inclinado (20,0°)');

// Agua del suelo en fracción (POWER) y en porcentaje (sensor).
assert.equal(L.aguaSuelo(0.61), '61 de 100');
assert.equal(L.aguaEnSuelo(0.61), 'agua en el suelo: 61 de 100');
assert.equal(L.aguaEnSuelo(61, false), 'agua en el suelo: 61 de 100');

// Temperatura y glosario.
assert.equal(L.temperatura(20), '20,0 °C');
assert.ok(L.GLOSARIO.length >= 8, 'el glosario necesita al menos 8 términos');
for (const [termino, explicacion] of L.GLOSARIO) {
  assert.ok(termino && explicacion && explicacion.length > 30, `término flojo: ${termino}`);
}

console.log('lenguaje.mjs OK');
