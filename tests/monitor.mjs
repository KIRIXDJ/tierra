// Pruebas del panel de monitoreo (sensores simulados): node tests/monitor.mjs
import { createRequire } from 'node:module';
import assert from 'node:assert';

const require = createRequire(import.meta.url);
const Monitor = require('../web/monitor.js');

const PARCELA = {
  id: 'la-esperanza', nombre: 'La Esperanza', cultivo: 'yuca', temperatura: 28.4,
  humedad_inicial: 18,
  sensores: [{ id: 'ESP-01' }, { id: 'ESP-02' }],
};
const AHORA = Date.parse('2026-11-13T16:30:00-04:00'); // 16:30 en Santo Domingo

// 1. Misma hora → mismas lecturas (la serie es estable, no aleatoria).
const a = Monitor.lecturas(PARCELA, AHORA, { humedad: 18 });
const b = Monitor.lecturas(PARCELA, AHORA, { humedad: 18 });
assert.deepStrictEqual(a, b, 'la simulación debe ser determinista');

// 2. Una lectura por sensor, con rangos físicos razonables.
assert.strictEqual(a.length, 2);
assert.strictEqual(a[0].id, 'ESP-01');
for (const s of a) {
  assert.ok(s.humedad >= 5 && s.humedad <= 60, `humedad ${s.humedad}`);
  assert.ok(s.humedad_aire >= 35 && s.humedad_aire <= 96, `aire ${s.humedad_aire}`);
  assert.ok(s.temperatura > 15 && s.temperatura < 45, `temp ${s.temperatura}`);
  assert.ok(s.luz >= 0 && s.luz <= 90000, `luz ${s.luz}`);
  assert.ok(s.bateria >= 3.5 && s.bateria <= 4.1, `batería ${s.bateria}`);
  assert.strictEqual(s.online, true);
}

// 3. Luz: de noche 0, a mediodía alta (hora local de Santo Domingo, UTC-4).
const madrugada = Monitor.lecturas(PARCELA, Date.parse('2026-11-13T07:00:00Z'), {});
assert.strictEqual(madrugada[0].luz, 0, 'a las 03:00 no hay luz');
const mediodia = Monitor.lecturas(PARCELA, Date.parse('2026-11-13T16:00:00Z'), {});
assert.ok(mediodia[0].luz > 50000, `a mediodía debería haber luz: ${mediodia[0].luz}`);

// 4. El riego sube la humedad y la lluvia también.
const seca = Monitor.lecturas(PARCELA, AHORA, { humedad: 18 })[0].humedad;
const regando = Monitor.lecturas(PARCELA, AHORA, { humedad: 18, riego: true })[0].humedad;
const conLluvia = Monitor.lecturas(PARCELA, AHORA, { humedad: 18, lluvia_mm_h: 4 })[0].humedad;
assert.ok(regando > seca, 'regar debe subir la humedad');
assert.ok(conLluvia > seca, 'la lluvia debe subir la humedad');

// 5. Serie de 24 h para el minigráfico: 48 puntos, ordenados y en rango.
const serie = Monitor.historial(PARCELA, AHORA, { humedad: 18 });
assert.strictEqual(serie.length, 48);
assert.ok(serie[0].t < serie[serie.length - 1].t);
assert.ok(serie.every((p) => p.valor >= 5 && p.valor <= 60));

// 6. Resumen del bot en una línea.
const texto = Monitor.resumen(PARCELA, a[0], { riego: true, techo: false });
assert.match(texto, /La Esperanza/);
assert.match(texto, /humedad \d/);
assert.match(texto, /°C/);
assert.match(texto, /riego encendido/);
assert.match(texto, /techo abierto/);
assert.strictEqual(Monitor.resumen(null, null, {}), 'No tengo ese dato.');

// 7. Estado del bot de Telegram: solo vale si es reciente.
const estadoBot = {
  actualizado: new Date(AHORA - 20000).toISOString(),
  parcelas: { 'la-esperanza': { riego: false, techo: true, ventilacion: false } },
  ultimo: { texto: '/techo on', respuesta: 'Techo cerrado.' },
};
const remoto = Monitor.estadoRemoto(estadoBot, AHORA);
assert.ok(remoto && remoto.conectado);
assert.strictEqual(remoto.parcelas['la-esperanza'].techo, true);
assert.strictEqual(Monitor.estadoRemoto(estadoBot, AHORA + 10 * 60000), null,
  'un estado de hace 10 minutos no se usa');
assert.strictEqual(Monitor.estadoRemoto(null, AHORA), null);
assert.strictEqual(Monitor.estadoRemoto({ actualizado: 'ayer' }, AHORA), null);

// 8. Fusión: el bot manda, salvo que el agricultor haya tocado el control.
const local = { id: 'la-esperanza', riego: true, techo: false, ventilacion: true };
const fusion = Monitor.fusionar(local, remoto, {});
assert.strictEqual(fusion.riego, false);
assert.strictEqual(fusion.techo, true);
const manual = Monitor.fusionar(local, remoto, { techo: false });
assert.strictEqual(manual.techo, false, 'el control manual gana');
assert.deepStrictEqual(
  Monitor.fusionar({ id: 'x' }, null, {}),
  { id: 'x', riego: false, techo: false, ventilacion: false },
);

// 9. Mandos por Telegram: solo cuentan los actuadores que se pidieron.
assert.deepStrictEqual(
  Monitor.mandosDelHistorial([{ texto: '/techo on' }, { texto: '/riego off' }]),
  { techo: true, riego: false });
assert.deepStrictEqual(
  Monitor.mandosDelHistorial([{ texto: '/riego on' }, { texto: '/riego off' }]),
  { riego: false }, 'el más reciente manda');
assert.deepStrictEqual(
  Monitor.mandosDelHistorial([{ texto: '/techo on' }, { texto: '/auto' }]), {},
  '/auto borra los mandos');
assert.deepStrictEqual(Monitor.mandosDelHistorial(null), {});
assert.deepStrictEqual(
  Monitor.mandosDelHistorial([{ texto: '/ventilar on' }]), { ventilacion: true });
assert.deepStrictEqual(
  Monitor.mandosDelHistorial([{ texto: '/clima' }]), {}, 'un comando de lectura no manda nada');

// 10. Utilidades.
assert.strictEqual(Monitor.acotar(120, 0, 100), 100);
assert.strictEqual(Monitor.acotar(-5, 0, 100), 0);
assert.strictEqual(Monitor.semilla('la-esperanza'), Monitor.semilla('la-esperanza'));
assert.notStrictEqual(Monitor.semilla('la-esperanza'), Monitor.semilla('el-hoyo'));
assert.match(Monitor.formatoHora(AHORA), /^\d{2}:\d{2}$/);

console.log('OK');
