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

// 8. Análisis de foto: píxeles sintéticos con resultado conocido.
function imagen(color, w = 40, h = 40, mitad = null) {
  const datos = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const i = (y * w + x) * 4;
      const c = mitad && x >= w / 2 ? mitad : color;
      datos[i] = c[0]; datos[i + 1] = c[1]; datos[i + 2] = c[2]; datos[i + 3] = 255;
    }
  }
  return { datos, w, h };
}
const VERDE = [40, 140, 50];
const AMARILLO = [220, 210, 60];

let img = imagen(VERDE);
let foto = Vision.analizarFoto(img.datos, img.w, img.h);
assert.ok(foto.verde_pct > 95, `verde ${foto.verde_pct}`);
assert.match(foto.hallazgo, /sin signos claros/);

img = imagen(VERDE, 40, 40, AMARILLO);          // mitad verde, mitad amarilla
foto = Vision.analizarFoto(img.datos, img.w, img.h);
assert.ok(foto.amarillo_pct > 40, `amarillo ${foto.amarillo_pct}`);
assert.match(foto.hallazgo, /clorosis/);

img = imagen([128, 120, 110]);                   // todo suelo/gris
foto = Vision.analizarFoto(img.datos, img.w, img.h);
assert.match(foto.hallazgo, /No se ve planta/);

assert.strictEqual(Vision.analizarFoto(null, 0, 0), null);

console.log('OK');
