/* Elio y los textos de la capa agrícola: funciones puras, sin DOM.
   Se usa desde index.html (window.Elio) y desde tests/elio.mjs (module.exports). */
(function () {
  'use strict';

  function numero(valor, decimales = 1) {
    return valor === null || valor === undefined ? 'sin dato' : Number(valor).toFixed(decimales);
  }

  function diasDesde(iso, ahora = Date.now()) {
    if (!iso) { return null; }
    return Math.max(0, Math.floor((ahora - new Date(iso).getTime()) / 86400000));
  }

  function textoLluvia(bloque) {
    if (!bloque || bloque['30d_mm'] === null || bloque['30d_mm'] === undefined) {
      return 'Lluvia 30 d: <b>sin dato</b>.';
    }
    const pct = bloque.pct;
    const sentido = pct === null || pct === undefined ? ''
      : ` (${pct > 0 ? '+' : ''}${Math.round(pct)} % sobre lo normal)`;
    return `Lluvia 30 d: <b>${numero(bloque['30d_mm'])} mm</b>${sentido}.`
      + ` Normal ${numero(bloque.normal_mm)} mm.`;
  }

  function textoTemperatura(bloque) {
    if (!bloque || bloque.media === null || bloque.media === undefined) {
      return 'Temperatura: <b>sin dato</b>.';
    }
    const delta = bloque.delta;
    const sentido = delta === null || delta === undefined ? ''
      : `, ${delta > 0 ? '+' : ''}${numero(delta)} °C sobre lo normal`;
    return `Temperatura media: <b>${numero(bloque.media)} °C</b>${sentido}.`;
  }

  function textoHumedad(bloque) {
    if (!bloque || bloque.valor === null || bloque.valor === undefined) {
      return 'Humedad superficial (0–7 cm): <b>sin dato</b>.';
    }
    const cambio = bloque.cambio_7d;
    const sentido = cambio === null || cambio === undefined ? ''
      : `, ${cambio > 0 ? '+' : ''}${numero(cambio, 2)} en 7 días`;
    return `Humedad superficial (0–7 cm): <b>${numero(bloque.valor, 2)} m³/m³</b>${sentido}.`
      + ' Sin banda histórica comparable.';
  }

  /* Índice con los pesos del agricultor sobre los componentes que ya calculó el motor. */
  function indicesRotaciones(estrategia, pesoAgua, pesoDiversidad) {
    const c = (estrategia && estrategia.componentes) || {};
    if (c.agua === null || c.agua === undefined
      || c.diversidad === null || c.diversidad === undefined) {
      return null;
    }
    if ((pesoAgua || 0) + (pesoDiversidad || 0) === 0) { return estrategia.indice; }
    return Math.round(100 * (pesoAgua * c.agua + pesoDiversidad * c.diversidad)
      / (10 * (pesoAgua + pesoDiversidad)));
  }

  const SIN_DATO = 'No tengo ese dato. Puedo hablarte de la temporada y de las rotaciones de esta finca.';

  function responderElio(pregunta, contexto) {
    const texto = String(pregunta || '').toLowerCase();
    const c = contexto || {};
    const nombre = c.nombre || 'esta finca';
    if (!texto.trim()) {
      return 'Escríbeme una pregunta sobre la temporada o las rotaciones.';
    }
    if (/riego|válvula|valvula|bomba|activa|enciende/.test(texto)) {
      return 'No controlo dispositivos en esta fase. Solo leo datos y explico lo que hay.';
    }
    if (/ndvi/.test(texto)) {
      return 'NDVI es un índice de verde de la vegetación medido por satélite: alto significa'
        + ' follaje sano. Esta herramienta no lo calcula todavía: no tengo ese dato.';
    }
    if (/evapotranspiraci/.test(texto)) {
      return 'La evapotranspiración es el agua que sale del suelo por evaporación y por las'
        + ' plantas. Esta herramienta no la mide: no tengo ese dato.';
    }
    if (/lluvia|seco|sequía|sequia|riega/.test(texto)) {
      const l = c.reciente && c.reciente.lluvia;
      if (!l || l['30d_mm'] === null || l['30d_mm'] === undefined) { return SIN_DATO; }
      const estado = l.estado === 'por_debajo' ? 'por debajo de lo normal'
        : l.estado === 'por_encima' ? 'por encima de lo normal' : 'dentro de lo normal';
      return `En ${nombre} cayeron ${l['30d_mm'].toFixed(1)} mm en 30 días,`
        + ` frente a una normal de ${(l.normal_mm ?? 0).toFixed(1)} mm (${estado}).`
        + ' Fuente: Open-Meteo, no NASA. Es una estimación de celda de modelo.';
    }
    if (/temperatura|calor|frío|frio/.test(texto)) {
      const t = c.reciente && c.reciente.temperatura;
      if (!t || t.media === null || t.media === undefined) { return SIN_DATO; }
      const d = t.delta ?? 0;
      return `La temperatura media de los últimos 30 días en ${nombre} fue`
        + ` ${t.media.toFixed(1)} °C, ${d >= 0 ? 'por encima' : 'por debajo'} de lo normal`
        + ` en ${Math.abs(d).toFixed(1)} °C. Fuente: Open-Meteo, no NASA.`;
    }
    if (/rotaci|siembro|conviene|alternativa|recomiend/.test(texto)) {
      const estrategias = (c.rotaciones && c.rotaciones.estrategias) || [];
      if (!estrategias.length) { return SIN_DATO; }
      const mejor = [...estrategias].sort((a, b) => b.indice - a.indice)[0];
      if (/por qué|por que/.test(texto)) {
        return `Te sugiero ${mejor.titulo} porque: ${(mejor.motivos || []).join('; ')}.`
          + ' Es un índice orientativo, no una recomendación agronómica.';
      }
      if (/riesgo|revisar/.test(texto)) {
        return `Con ${mejor.titulo} revisa con un agrónomo: ${(mejor.riesgos || []).join('; ')}.`
          + ` Faltan datos: ${(mejor.datos_faltantes || []).join('; ')}.`;
      }
      return `Con más puntaje aparece ${mejor.titulo} (${mejor.indice}/100, orientativo).`
        + ' Se apoya en la climatología de NASA POWER y en la temporada actual.'
        + ' Valídalo con un agrónomo local antes de cambiar la siembra.';
    }
    if (/temporada|vamos|estado/.test(texto)) {
      const l = c.reciente && c.reciente.lluvia;
      if (!l) { return SIN_DATO; }
      return `Temporada en ${nombre}: ${l['30d_mm'] === null || l['30d_mm'] === undefined
        ? 'sin dato de lluvia'
        : `${l['30d_mm'].toFixed(1)} mm en 30 días (${l.estado || 'sin estado'})`}.`
        + ' Fuente: Open-Meteo (no NASA) y climatología ERA5. Apoyo, no monitoreo de parcela.';
    }
    return SIN_DATO;
  }

  const Elio = {
    numero, diasDesde, textoLluvia, textoTemperatura, textoHumedad,
    indicesRotaciones, responderElio,
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = Elio; }
  if (typeof window !== 'undefined') { window.Elio = Elio; }
}());
