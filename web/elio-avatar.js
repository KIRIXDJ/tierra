/* Avatar de Elio: orbe de puntos sobre una esfera, sin DOM ni timers.
   Se usa desde index.html (window.ElioAvatar) y desde tests/elio-avatar.mjs. */
(function () {
  'use strict';

  const NOMBRE = 'Elio';
  const VALIDOS = ['reposo', 'pensando', 'habla'];
  const DORADO = Math.PI * (3 - Math.sqrt(5)); // ángulo áureo: puntos repartidos, sin Math.random
  let actual = 'reposo';

  /* Un solo Elio en pantalla: el estado del módulo y el de la instancia son el mismo. */
  function estado(nuevo) {
    actual = VALIDOS.includes(nuevo) ? nuevo : 'reposo';
    return actual;
  }

  function crear(canvas, opciones) {
    const op = opciones || {};
    const ancho = op.ancho ?? (canvas && canvas.width);
    const alto = op.alto ?? (canvas && canvas.height);
    const total = op.puntos ?? 90;
    let ctx = canvas && typeof canvas.getContext === 'function' ? canvas.getContext('2d') : null;
    const medio = Math.min(ancho, alto) / 2;

    /* Nube de puntos fija: misma entrada, mismo fotograma. */
    const esfera = [];
    for (let i = 0; i < total; i += 1) {
      const y = total < 2 ? 0 : 1 - (i / (total - 1)) * 2;
      const radio = Math.sqrt(Math.max(0, 1 - y * y));
      esfera.push([Math.cos(DORADO * i) * radio, y, Math.sin(DORADO * i) * radio]);
    }

    function circulo(x, y, tamano) {
      ctx.beginPath();
      ctx.arc(x, y, tamano, 0, Math.PI * 2);
      ctx.fill();
    }

    function anillo(cx, cy, radio, cantidad, fase, tamano, color) {
      ctx.fillStyle = color;
      for (let i = 0; i < cantidad; i += 1) {
        const a = fase + (i / cantidad) * Math.PI * 2;
        circulo(cx + Math.cos(a) * radio, cy + Math.sin(a) * radio, tamano);
      }
    }

    function pintar(t) {
      if (!ctx || !ancho || !alto) { return; }
      const ms = Number(t) || 0;
      const cx = ancho / 2;
      const cy = alto / 2;
      const giro = ms * (actual === 'pensando' ? 0.0013 : 0.0008);
      ctx.clearRect(0, 0, ancho, alto);

      /* Halo: gradiente radial cian/verde; es lo único que no son puntos. */
      const halo = ctx.createRadialGradient(cx, cy, medio * 0.1, cx, cy, medio);
      halo.addColorStop(0, 'rgba(110, 245, 215, 0.32)');
      halo.addColorStop(0.55, 'rgba(60, 200, 190, 0.12)');
      halo.addColorStop(1, 'rgba(30, 120, 150, 0)');
      ctx.fillStyle = halo;
      circulo(cx, cy, medio);

      // Giro sobre Y y algo sobre X; z ordena el dibujo por profundidad para que se lea 3D.
      const proyecciones = [];
      const cosY = Math.cos(giro);
      const sinY = Math.sin(giro);
      const cosX = Math.cos(giro * 0.6);
      const sinX = Math.sin(giro * 0.6);
      for (const [x, y, z] of esfera) {
        const x1 = x * cosY - z * sinY;
        const z1 = x * sinY + z * cosY;
        proyecciones.push([x1, y * cosX - z1 * sinX, y * sinX + z1 * cosX]);
      }
      proyecciones.sort((a, b) => a[2] - b[2]);
      const radioOrbe = medio * 0.72;
      for (const [x, y, z] of proyecciones) {
        const prof = (z + 1) / 2; // 0 al fondo, 1 delante
        ctx.fillStyle = `hsla(${164 + 26 * prof}, 95%, ${48 + 22 * prof}%, ${0.18 + 0.82 * prof})`;
        circulo(cx + x * radioOrbe, cy + y * radioOrbe,
          Math.max(0.5, medio * (0.018 + 0.034 * prof)));
      }

      if (actual === 'pensando') {
        anillo(cx, cy, medio * 0.9, 28, giro * 1.6, medio * 0.03,
          'hsla(172, 95%, 70%, 0.85)');
      } else if (actual === 'habla') {
        // Dos anillos en contrafase: el latido de la voz.
        const pulso = 0.5 + 0.5 * Math.sin(ms / 180);
        anillo(cx, cy, medio * (0.78 + 0.1 * pulso), 32, giro * 1.2, medio * 0.03,
          'hsla(150, 85%, 70%, 0.9)');
        anillo(cx, cy, medio * (0.92 - 0.06 * pulso), 24, -giro * 1.2, medio * 0.022,
          'hsla(178, 85%, 66%, 0.55)');
      }
    }

    function destruir() {
      ctx = null;
    }

    return { pintar, estado, destruir };
  }

  const ElioAvatar = { NOMBRE, crear, estado };
  if (typeof module !== 'undefined' && module.exports) { module.exports = ElioAvatar; }
  if (typeof window !== 'undefined') { window.ElioAvatar = ElioAvatar; }
}());
