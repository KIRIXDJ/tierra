// Pruebas de la granja conectada (simulación): node tests/vision.mjs
import { createRequire } from 'node:module';
import assert from 'node:assert';

const require = createRequire(import.meta.url);
const Vision = require('../web/vision.js');

// 1. Humedad baja → riego; humedad alta → apagado.
let estado = Vision.parcelasIniciales();
let salida = Vision.evaluar(estado, { lluvia_mm_h: 0 });
assert.strictEqual(salida.parcelas[0].riego, true, 'A está seca (18 %) y debe regar');
assert.strictEqual(salida.parcelas[1].riego, false, 'B está a 33 % y no riega');
assert.ok(salida.avisos.some((a) => /riego activado/.test(a)));

// 2. Recuperar humedad apaga el riego (con histéresis).
estado = salida.parcelas.map((p) => (p.id === 'A' ? { ...p, humedad: 31 } : p));
salida = Vision.evaluar(estado, { lluvia_mm_h: 0 });
assert.strictEqual(salida.parcelas[0].riego, false);
assert.ok(salida.avisos.some((a) => /riego apagado/.test(a)));

// 3. Lluvia cierra el techo y suspende el riego.
estado = Vision.parcelasIniciales();
salida = Vision.evaluar(estado, { lluvia_mm_h: 4 });
assert.ok(salida.parcelas.every((p) => p.techo === true), 'con lluvia el techo se cierra');
assert.ok(salida.parcelas.every((p) => p.riego === false), 'con lluvia no se riega');
assert.ok(salida.avisos.some((a) => /Techo cerrado/.test(a)));

// 4. Sin cambios relevantes no hay avisos de actuador.
estado = Vision.parcelasIniciales().map((p) => ({ ...p, humedad: 40, techo: false }));
salida = Vision.evaluar(estado, { lluvia_mm_h: 0 });
assert.ok(!salida.avisos.some((a) => /riego activado|riego apagado/.test(a)));

// 5. Mensaje de Telegram con hora.
assert.match(Vision.mensajeTelegram(['X: algo'], '12:34'), /^\[12:34\] X: algo$/);
assert.match(Vision.mensajeTelegram([], '09:00'), /Sin cambios/);

// 6. Resumen.
estado = Vision.parcelasIniciales();
salida = Vision.evaluar(estado, { lluvia_mm_h: 0 });
const r = Vision.resumen(salida.parcelas);
assert.strictEqual(r.total, 3);
assert.strictEqual(r.regando, 1);

// 7. Sin lectura de humedad no se decide nada (dato null).
const sinDato = [Vision.parcela('X', 'Parcela X', 'sorgo', null, 1)];
assert.strictEqual(Vision.evaluar(sinDato, { lluvia_mm_h: 0 }).parcelas[0].riego, false);

console.log('OK');
