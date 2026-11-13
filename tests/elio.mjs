// Pruebas de Elio: node tests/elio.mjs
import { createRequire } from 'node:module';
import assert from 'node:assert';

const require = createRequire(import.meta.url);
const Elio = require('../web/elio.js');

const reciente = {
  actualizado: '2026-11-12T10:00:00-04:00',
  fuente: { nombre: 'Open-Meteo', no_nasa: true },
  fincas: [{
    id: 'constanza',
    lluvia: { '30d_mm': 12.4, normal_mm: 45.1, pct: -72, estado: 'por_debajo' },
    temperatura: { media: 24.1, normal: 23.5, delta: 0.6 },
    humedad_superficial: { valor: 0.28, cambio_7d: -0.02 },
  }],
};
const rotaciones = {
  estrategias: [
    { id: 'actual', titulo: 'Rotación actual', indice: 50, motivos: ['es la de siempre'],
      riesgos: ['sin fuente'], datos_faltantes: ['textura de suelo'],
      componentes: { agua: 10, diversidad: 0 }, provisional: true },
    { id: 'alternativa_2', titulo: 'Yuca, maní y sorgo', indice: 88,
      motivos: ['diversifica'], riesgos: ['precio del sorgo'],
      datos_faltantes: ['rendimiento histórico'],
      componentes: { agua: 7.5, diversidad: 10 }, provisional: true },
  ],
};
const contexto = { nombre: 'Constanza', reciente: reciente.fincas[0], rotaciones };

// 1. Temporada con datos: cifra, porcentaje y fuente no NASA.
const lluvia = Elio.responderElio('¿está seco?', contexto);
assert.match(lluvia, /12\.4 mm/);
assert.match(lluvia, /45\.1 mm/);
assert.match(lluvia, /Open-Meteo/);
assert.match(lluvia, /no NASA/);

// 2. Rotación: elige la de mayor índice y avisa que es orientativo.
const rot = Elio.responderElio('¿qué rotación me conviene?', contexto);
assert.match(rot, /Yuca/);
assert.match(rot, /88\/100/);
assert.match(rot, /orientativo/);

// 3. Sin datos: no inventa.
const vacio = Elio.responderElio('¿cuánto llovió?', { nombre: 'Azua', reciente: null });
assert.match(vacio, /No tengo ese dato/);

// 4. Actuadores: no controla nada.
assert.match(Elio.responderElio('activa el riego', contexto), /No controlo dispositivos/);

// 5. Toda cifra lleva fuente.
assert.match(Elio.responderElio('temperatura', contexto), /Open-Meteo/);

// 6. Índice con prioridades: todo peso al agua favorece la de agua baja.
assert.strictEqual(Elio.indicesRotaciones({ componentes: { agua: 10, diversidad: 0 } }, 10, 0), 100);
assert.strictEqual(Elio.indicesRotaciones({ componentes: { agua: 10, diversidad: 0 } }, 0, 10), 0);

// 7. Frescura.
assert.strictEqual(Elio.diasDesde('2026-11-12T10:00:00-04:00',
  new Date('2026-11-13T10:00:00-04:00').getTime()), 1);
assert.strictEqual(Elio.diasDesde(null), null);

// 8. Textos de la tarjeta.
assert.match(Elio.textoHumedad({ valor: 0.28, cambio_7d: -0.02 }), /0–7 cm/);
assert.match(Elio.textoLluvia({ '30d_mm': null }), /sin dato/);

// 9. Escenario de sequía: la de peor componente de agua pierde más; la de agua 10 no pierde.
const seco = { componentes: { agua: 5, diversidad: 5 } };
const bueno = { componentes: { agua: 10, diversidad: 0 } };
assert.strictEqual(Elio.indiceEscenario(bueno, 5, 5, -40), Elio.indicesRotaciones(bueno, 5, 5));
assert.ok(Elio.indiceEscenario(seco, 5, 5, -40) < Elio.indicesRotaciones(seco, 5, 5));
assert.strictEqual(Elio.indiceEscenario(seco, 5, 5, 0), Elio.indicesRotaciones(seco, 5, 5));
assert.strictEqual(Elio.indiceEscenario(seco, 5, 5, 20), Elio.indicesRotaciones(seco, 5, 5));

console.log('OK');
