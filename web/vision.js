/* Granja conectada: lógica de la vista "cómo sería".
   Funciones puras, sin DOM: deciden riego y techo a partir de las lecturas.
   Es una SIMULACIÓN de producto, no hay hardware conectado. */

(function () {
  'use strict';

  const UMBRAL_RIEGO = 25;      // % de humedad por debajo del cual se riega
  const HISTERESIS = 5;         // se apaga al superar umbral + histeresis
  const LLUVIA_TECHO = 0.2;     // mm/h a partir de los cuales se cierra el techo
  const CALOR_VENTILACION = 26; // °C a partir de los cuales se ventila el invernadero

  function parcela(id, nombre, cultivo, humedad, area) {
    return {
      id, nombre, cultivo,
      humedad: humedad === undefined ? null : humedad,
      area_ha: area === undefined ? null : area,
      riego: false,
      techo: false,
      ventilacion: false,
      sensores: 2,
    };
  }

  /* Estado inicial de las parcelas de ejemplo (valores de la simulación). */
  function parcelasIniciales() {
    return [
      parcela('A', 'Parcela A', 'yuca', 18, 1.2),
      parcela('B', 'Parcela B', 'frijol', 33, 0.8),
      parcela('C', 'Parcela C', 'maíz', 26, 1.5),
    ];
  }

  /* Una lectura = {lluvia_mm_h}. Devuelve el estado nuevo y los avisos. */
  function evaluar(parcelas, lectura, umbral = UMBRAL_RIEGO) {
    const lluvia = Number((lectura || {}).lluvia_mm_h || 0);
    const avisos = [];
    const estado = parcelas.map((p) => {
      const humedad = p.humedad;
      let riego = p.riego;
      if (humedad !== null && humedad !== undefined) {
        if (!riego && humedad < umbral) {
          riego = true;
          avisos.push(`${p.nombre}: humedad ${humedad} % bajo el umbral ${umbral} % → riego activado.`);
        } else if (riego && humedad > umbral + HISTERESIS) {
          riego = false;
          avisos.push(`${p.nombre}: humedad ${humedad} % recuperada → riego apagado.`);
        }
      }
      // Con lluvia no se riega aunque falte humedad: sería tirar agua.
      if (riego && lluvia >= LLUVIA_TECHO) {
        riego = false;
        avisos.push(`${p.nombre}: llueve (${lluvia} mm/h) → riego suspendido.`);
      }
      // Ventilación: abre con calor y sin lluvia (como el invernadero de Hiroki).
      const temperatura = p.temperatura === null || p.temperatura === undefined
        ? null : Number(p.temperatura);
      let ventilacion = p.ventilacion;
      if (temperatura !== null && lluvia < LLUVIA_TECHO) {
        if (!ventilacion && temperatura >= CALOR_VENTILACION) {
          ventilacion = true;
          avisos.push(`${p.nombre}: ${temperatura} °C → ventilación abierta.`);
        } else if (ventilacion && temperatura < CALOR_VENTILACION - 2) {
          ventilacion = false;
          avisos.push(`${p.nombre}: ${temperatura} °C → ventilación cerrada.`);
        }
      }
      if (lluvia >= LLUVIA_TECHO && ventilacion) {
        ventilacion = false;
        avisos.push(`${p.nombre}: llueve → ventilación cerrada para no mojar.`);
      }
      const techo = lluvia >= LLUVIA_TECHO;
      if (techo !== p.techo) {
        avisos.push(techo
          ? `Techo cerrado: lluvia de ${lluvia} mm/h sobre ${p.nombre}.`
          : `Techo abierto: sin lluvia sobre ${p.nombre}.`);
      }
      return { ...p, riego, techo, ventilacion };
    });
    return { parcelas: estado, avisos };
  }

  /* Mensaje con el formato que se enviaría por Telegram. */
  function mensajeTelegram(avisos, hora = '12:00') {
    if (!avisos.length) {
      return `[${hora}] Sin cambios: todo dentro de lo previsto.`;
    }
    return avisos.map((aviso) => `[${hora}] ${aviso}`).join('\n');
  }

  /* Resumen llano para la tarjeta de la finca. */
  function resumen(parcelas) {
    const regando = parcelas.filter((p) => p.riego).length;
    const cerrados = parcelas.filter((p) => p.techo).length;
    const secas = parcelas.filter((p) => p.humedad !== null && p.humedad < UMBRAL_RIEGO).length;
    const ventilando = parcelas.filter((p) => p.ventilacion).length;
    return { regando, techos_cerrados: cerrados, ventilando,
             parcelas_secas: secas, total: parcelas.length };
  }


  /* ---- Análisis de una foto de cultivo ----
     Mide color, no "entiende" la hoja: clasifica píxeles en verde sano, amarillo
     (clorosis) y marrón (necrosis). Es un indicador honesto, no un modelo de
     visión validado. `datos` es un Uint8ClampedArray RGBA. */
  function clasificarPixel(r, g, b) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const v = max / 255;
    const s = max === 0 ? 0 : (max - min) / max;
    let h = 0;
    if (max !== min) {
      if (max === r) { h = 60 * (((g - b) / (max - min)) % 6); }
      else if (max === g) { h = 60 * ((b - r) / (max - min) + 2); }
      else { h = 60 * ((r - g) / (max - min) + 4); }
    }
    if (h < 0) { h += 360; }
    if (s < 0.15 || v < 0.12) { return 'suelo'; }        // gris, sombra, tierra clara
    if (h >= 70 && h <= 165) { return 'verde'; }          // follaje
    if (h >= 45 && h < 70 && v > 0.45) { return 'amarillo'; } // clorosis
    if (h >= 10 && h < 45) { return 'marron'; }           // necrosis / tierra
    return 'otro';
  }

  function analizarFoto(datos, ancho, alto, paso = 4) {
    const total = { verde: 0, amarillo: 0, marron: 0, suelo: 0, otro: 0 };
    let n = 0;
    if (!datos || !ancho || !alto) { return null; }
    for (let y = 0; y < alto; y += paso) {
      for (let x = 0; x < ancho; x += paso) {
        const i = (y * ancho + x) * 4;
        if (i + 3 > datos.length) { continue; }
        if (datos[i + 3] < 128) { continue; }            // transparente
        total[clasificarPixel(datos[i], datos[i + 1], datos[i + 2])] += 1;
        n += 1;
      }
    }
    if (!n) { return null; }
    const planta = total.verde + total.amarillo + total.marron;
    const pct = (k) => Math.round((total[k] / n) * 1000) / 10;
    const pctPlanta = (k) => (planta ? Math.round((total[k] / planta) * 1000) / 10 : null);

    let hallazgo;
    let confianza;
    if (planta / n < 0.15) {
      hallazgo = 'No se ve planta suficiente en la foto: acércate a una hoja o a una mata.';
      confianza = 0.35;
    } else if (pctPlanta('amarillo') > 25) {
      hallazgo = 'Manchas amarillas extensas: compatible con clorosis o falta de nutrientes.';
      confianza = 0.62;
    } else if (pctPlanta('marron') > 20) {
      hallazgo = 'Tejido marrón abundante: compatible con necrosis o daño por plaga.';
      confianza = 0.6;
    } else if (pctPlanta('amarillo') > 10) {
      hallazgo = 'Algo de amarilleo en hoja: vigilar en los próximos días.';
      confianza = 0.55;
    } else {
      hallazgo = 'Follaje mayormente verde y uniforme: sin signos claros de problema.';
      confianza = 0.7;
    }
    return {
      verde_pct: pct('verde'), amarillo_pct: pct('amarillo'), marron_pct: pct('marron'),
      suelo_pct: pct('suelo'), planta_pct: Math.round((planta / n) * 1000) / 10,
      hallazgo, confianza, pixeles: n,
    };
  }


  /* ---- Bot de Telegram: interpreta lo que escribe el agricultor ----
     Puro: recibe el texto y el estado, devuelve la respuesta y qué cambiar.
     En producción esto lo haría un bot real con su token en el servidor. */
  function interpretarComando(texto, contexto) {
    const c = contexto || {};
    const parcela = c.parcela || {};
    const estado = c.estado || {};
    const t = String(texto || '').trim().toLowerCase();
    const nombre = parcela.nombre || 'tu parcela';
    const cambios = {};
    const ayuda = [
      'Comandos:',
      '/estado — cómo va la parcela',
      '/riego on|off — abrir o cerrar el riego',
      '/ventilacion on|off — abrir o cerrar la ventilación',
      '/techo on|off — cerrar o abrir el techo',
      '/auto — volver a automático',
      '/foto — analizar la última foto',
    ].join('\n');

    if (!t || t === '/ayuda' || t === 'ayuda' || t === '/start') {
      return { respuesta: `Hola. Soy el bot de ${nombre}.\n\n${ayuda}`, cambios };
    }
    if (t === '/estado' || t === 'estado') {
      return {
        respuesta: `*${nombre}* (${parcela.cultivo || 'sin cultivo'}, ${parcela.area_ha ?? '?'} ha)\n`
          + `Humedad: ${estado.humedad ?? '?'} %\n`
          + `Temperatura: ${parcela.temperatura ?? '?'} °C\n`
          + `Riego: ${estado.riego ? 'encendido' : 'apagado'}\n`
          + `Ventilación: ${estado.ventilacion ? 'abierta' : 'cerrada'}\n`
          + `Techo: ${estado.techo ? 'cerrado' : 'abierto'}\n`
          + `${estado.humedad !== null && estado.humedad < UMBRAL_RIEGO
            ? '⚠️ Falta agua: por debajo del umbral.' : 'Sin alertas.'}`,
        cambios,
      };
    }
    const orden = (clave) => {
      if (/(\bon\b|encend|abre|abrir|activa|cierra|cerrar@sí)/.test(t)) { return true; }
      if (/(\boff\b|apag|cierra|cerrar|desactiva)/.test(t)) { return false; }
      return null;
    };
    if (/\/riego|riega|regar/.test(t)) {
      const valor = orden(t);
      if (valor === null) {
        return { respuesta: '¿Riego on o riego off?', cambios };
      }
      cambios.riego = valor;
      return { respuesta: valor ? `Riego abierto en ${nombre}.` : `Riego cerrado en ${nombre}.`, cambios };
    }
    if (/\/ventilacion|ventila/.test(t)) {
      const valor = orden(t);
      if (valor === null) {
        return { respuesta: '¿Ventilación on o ventilación off?', cambios };
      }
      cambios.ventilacion = valor;
      return { respuesta: valor ? 'Ventilación abierta.' : 'Ventilación cerrada.', cambios };
    }
    if (/\/techo|techo|lona/.test(t)) {
      const valor = orden(t);
      if (valor === null) {
        return { respuesta: '¿Techo on (cerrado) o techo off (abierto)?', cambios };
      }
      cambios.techo = valor;
      return { respuesta: valor ? 'Techo cerrado.' : 'Techo abierto.', cambios };
    }
    if (/\/auto|automatico|automático/.test(t)) {
      cambios.riego = null;
      cambios.ventilacion = null;
      cambios.techo = null;
      return { respuesta: 'Vuelto a modo automático: decido yo con los sensores.', cambios };
    }
    if (/\/foto|foto|fotografia/.test(t)) {
      return {
        respuesta: 'Mándame una foto de la hoja y te digo qué color veo. '
          + 'No diagnostico enfermedades: eso lo confirma un agrónomo.',
        cambios,
      };
    }
    if (/hola|buenas/.test(t)) {
      return { respuesta: `Hola. Soy el bot de ${nombre}.\n\n${ayuda}`, cambios };
    }
    return {
      respuesta: 'No entendí. ' + ayuda,
      cambios,
    };
  }

  const Vision = {
    UMBRAL_RIEGO, HISTERESIS, LLUVIA_TECHO, CALOR_VENTILACION,
    clasificarPixel, analizarFoto, interpretarComando,
    parcela, parcelasIniciales, evaluar, mensajeTelegram, resumen,
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = Vision; }
  if (typeof window !== 'undefined') { window.Vision = Vision; }
}());
