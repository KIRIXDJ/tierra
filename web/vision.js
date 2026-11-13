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

  const Vision = {
    UMBRAL_RIEGO, HISTERESIS, LLUVIA_TECHO, CALOR_VENTILACION,
    parcela, parcelasIniciales, evaluar, mensajeTelegram, resumen,
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = Vision; }
  if (typeof window !== 'undefined') { window.Vision = Vision; }
}());
