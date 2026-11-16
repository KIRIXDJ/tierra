/* Monitoreo de la finca: lógica pura, sin DOM.
   Sensores y actuadores son SIMULACIÓN (hoy no hay hardware instalado).
   El clima y el suelo vienen de snapshots reales: Open-Meteo/ERA5 y NASA POWER.
   Se usa desde index.html (window.Monitor) y desde tests/monitor.mjs. */
(function () {
  'use strict';

  const DOS_PI = Math.PI * 2;
  const ZONA = 'America/Santo_Domingo';

  function acotar(valor, minimo, maximo) {
    return Math.min(maximo, Math.max(minimo, valor));
  }

  function redondear(valor, decimales = 1) {
    const factor = 10 ** decimales;
    return Math.round(valor * factor) / factor;
  }

  /* Semilla estable por texto: la misma parcela da la misma serie siempre. */
  function semilla(texto) {
    let valor = 7;
    for (let i = 0; i < String(texto).length; i += 1) {
      valor = (valor * 31 + String(texto).charCodeAt(i)) % 100000;
    }
    return valor;
  }

  function horaLocal(ahora) {
    const partes = new Intl.DateTimeFormat('es-DO', {
      timeZone: ZONA, hour: 'numeric', minute: 'numeric', hour12: false,
    }).formatToParts(new Date(ahora));
    const hora = Number((partes.find((p) => p.type === 'hour') || {}).value || 12);
    const minuto = Number((partes.find((p) => p.type === 'minute') || {}).value || 0);
    return hora + minuto / 60;
  }

  /* Luz aproximada por la altura del sol entre las 6 y las 18 h. */
  function luzSolar(hora) {
    const elevacion = Math.sin(((hora - 6) / 12) * Math.PI);
    if (elevacion <= 0) { return 0; }
    return Math.round(90000 * elevacion);
  }

  /* Lecturas por sensor. opciones: humedad, lluvia_mm_h, riego, techo, ahora. */
  function lecturas(parcela, ahora, opciones) {
    const op = opciones || {};
    const hora = horaLocal(ahora);
    const lluvia = Number(op.lluvia_mm_h || 0);
    const base = Number(op.humedad !== undefined && op.humedad !== null
      ? op.humedad : parcela.humedad_inicial);
    const horasDesdeEpoch = ahora / 3600000;
    const fase = semilla(parcela.id) % 7;
    const humedad = acotar(
      base + 1.8 * Math.sin(horasDesdeEpoch / 7.3 + fase) + (op.riego ? 7 : 0) + lluvia * 0.8,
      5, 60,
    );
    const tempAire = Number(parcela.temperatura !== null && parcela.temperatura !== undefined
      ? parcela.temperatura : 24)
      + 2.6 * Math.sin(((hora - 9) / 24) * DOS_PI) - 1.2;
    const tempSuelo = tempAire - 2.2 + 0.6 * Math.sin(((hora - 12) / 24) * DOS_PI);
    const humedadAire = acotar(
      88 - (tempAire - 22) * 2.4 - (op.techo ? 6 : 0),
      35, 96,
    );
    const luz = luzSolar(hora);
    const bateria = 3.6 + 0.45 * (0.5 + 0.5 * Math.sin(horasDesdeEpoch / 13 + fase));
    const sensores = (parcela.sensores && parcela.sensores.length)
      ? parcela.sensores : [{ id: 'ESP-01' }];
    return sensores.map((sensor, indice) => ({
      id: sensor.id,
      humedad: redondear(acotar(humedad + indice * 0.7, 5, 60)),
      humedad_aire: Math.round(acotar(humedadAire - indice * 1.5, 35, 96)),
      temperatura: redondear(tempAire + indice * 0.2),
      temperatura_suelo: redondear(tempSuelo - indice * 0.3),
      luz: Math.max(0, luz - indice * 400),
      bateria: redondear(bateria - indice * 0.03, 2),
      online: true,
    }));
  }

  /* Serie de las últimas 24 h para el minigráfico. */
  function historial(parcela, ahora, opciones) {
    const op = opciones || {};
    const paso = 30 * 60000;
    const puntos = [];
    const lluvia = Number(op.lluvia_mm_h || 0);
    for (let i = 47; i >= 0; i -= 1) {
      const t = Math.floor(ahora / paso) * paso - i * paso;
      const valor = lecturas(parcela, t, {
        humedad: op.humedad, lluvia_mm_h: lluvia * (i < 4 ? 1 : 0),
      })[0].humedad;
      puntos.push({ t, valor });
    }
    return puntos;
  }

  /* Texto breve del bot para /estado. */
  function resumen(parcela, sensor, estado) {
    if (!parcela || !sensor) { return 'No tengo ese dato.'; }
    const e = estado || {};
    const techo = e.techo ? 'techo cerrado' : 'techo abierto';
    const riego = e.riego ? 'riego encendido' : 'riego apagado';
    return `${parcela.nombre}: humedad ${sensor.humedad} %, aire ${sensor.temperatura} °C,`
      + ` ${riego}, ${techo}.`;
  }

  /* Estado que escribe el bot real de Telegram (o null si no hay / está viejo). */
  function estadoRemoto(datos, ahora, frescura_ms) {
    if (!datos || !datos.parcelas || !datos.actualizado) { return null; }
    const cuando = Date.parse(datos.actualizado);
    const frescura = frescura_ms === undefined ? 180000 : frescura_ms;
    if (!Number.isFinite(cuando) || Math.abs(ahora - cuando) > frescura) { return null; }
    return {
      conectado: true,
      cuando,
      parcelas: datos.parcelas,
      ultimo: datos.ultimo || null,
      historial: Array.isArray(datos.historial) ? datos.historial : [],
    };
  }

  /* Une el estado remoto con el local: el remoto manda en los actuadores. */
  function fusionar(local, remoto, manual) {
    const base = Object.assign(
      { riego: false, techo: false, ventilacion: false },
      local || {},
    );
    const deRemoto = remoto && remoto.parcelas && remoto.parcelas[base.id]
      ? remoto.parcelas[base.id] : null;
    ['riego', 'techo', 'ventilacion'].forEach((clave) => {
      if (deRemoto && typeof deRemoto[clave] === 'boolean') { base[clave] = deRemoto[clave]; }
      if (manual && typeof manual[clave] === 'boolean') { base[clave] = manual[clave]; }
    });
    return base;
  }

  /* Qué actuadores mandó el agricultor por Telegram (más reciente manda; /auto
     borra todo). Sirve para no pintar como «auto» lo que él puso a mano. */
  function mandosDelHistorial(historial) {
    const mandos = {};
    const lista = Array.isArray(historial) ? [...historial].reverse() : [];
    for (const item of lista) {
      const texto = String((item && item.texto) || '').toLowerCase();
      if (/\/auto/.test(texto)) { break; }
      const orden = texto.match(/\/(riego|techo|ventilar)\s+(on|off)/);
      if (!orden) { continue; }
      const clave = orden[1] === 'ventilar' ? 'ventilacion' : orden[1];
      if (!(clave in mandos)) { mandos[clave] = orden[2] === 'on'; }
    }
    return mandos;
  }

  function formatoHora(ms) {
    return new Intl.DateTimeFormat('es-DO', {
      timeZone: ZONA, hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(ms));
  }

  const Monitor = {
    acotar, semilla, horaLocal, luzSolar, lecturas, historial, resumen,
    estadoRemoto, fusionar, mandosDelHistorial, formatoHora,
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = Monitor; }
  if (typeof window !== 'undefined') { window.Monitor = Monitor; }
}());
