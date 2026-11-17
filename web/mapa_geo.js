/* Geometría del mapa de administración: pasar de lat/lon a metros de la finca,
   medir el área de un lote y validar que lo dibujado es una parcela razonable.
   Sin DOM y sin red: se prueba con Node (`tests/mapa_geo.mjs`).

   Convenios: vértices en lat/lon = [lat, lon] (orden de un pin de Google Maps);
   vértices en metros = [x este, y norte] respecto al centro de la finca.
   La proyección local es plana (radio terrestre × ángulo): con lotes de menos de
   ~2 km el error frente a Mercator es despreciable. */

export const TAM_TESELA = 256;
export const RADIO_TIERRA = 6378137;

const rad = (grados) => (grados * Math.PI) / 180;

/* Píxel global (Web Mercator) del punto en ese zoom, como en las teselas de Esri
   (`tile/{z}/{y}/{x}`). */
export function mundoAPixel(lat, lon, zoom) {
  const n = 2 ** zoom;
  const x = ((lon + 180) / 360) * n * TAM_TESELA;
  const r = rad(lat);
  const y = ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n * TAM_TESELA;
  return { x, y };
}

/* Vuelta: píxel global -> lat/lon. La necesita panear y centrar el mapa. */
export function pixelAMundo(x, y, zoom) {
  const n = 2 ** zoom * TAM_TESELA;
  const lon = (x / n) * 360 - 180;
  const lat = (180 / Math.PI) * Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)));
  return { lat, lon };
}

/* Metros reales por píxel a esa latitud (Mercator se corrige por el coseno). */
export function metrosPorPixel(lat, zoom) {
  return (Math.cos(rad(lat)) * 2 * Math.PI * RADIO_TIERRA) / (TAM_TESELA * 2 ** zoom);
}

/* Centro del lote: media de sus vértices (suficiente para lotes de una finca). */
export function centroDe(puntos) {
  const total = puntos.reduce((acc, [lat, lon]) => ({ lat: acc.lat + lat, lon: acc.lon + lon }),
    { lat: 0, lon: 0 });
  return { lat: total.lat / puntos.length, lon: total.lon / puntos.length };
}

/* Lat/lon -> metros relativos al centro, con la escala real a esa latitud. */
/* Los metros que calcula `aMetros` llevan la y hacia el norte, pero el canvas del
   mapa pinta la y hacia abajo (como las teselas): al dibujar hay que cambiarle el
   signo o la parcela sale espejada. */
export function aMarcoDeDibujo(poligono) {
  return (poligono || []).map(([x, y]) => [x, -y]);
}

export function aMetros(poligonoLatLon, centro) {
  // Metros por grado: de latitud es constante; de longitud se encoge con el coseno.
  const metrosPorGrado = (2 * Math.PI * RADIO_TIERRA) / 360;
  const escala = metrosPorGrado * Math.cos(rad(centro.lat));
  const poligono_m = poligonoLatLon.map(([lat, lon]) => [
    (lon - centro.lon) * escala,
    (lat - centro.lat) * metrosPorGrado,
  ]);
  // `mpp` es la escala de dibujo a zoom 18, la que usa la herramienta para medir.
  return { poligono_m, mpp: metrosPorPixel(centro.lat, 18) };
}

/* Vuelta: metros de la finca -> lat/lon (para editar una finca ya registrada). */
export function deMetros(poligono_m, centro) {
  const metrosPorGrado = (2 * Math.PI * RADIO_TIERRA) / 360;
  const escala = metrosPorGrado * Math.cos(rad(centro.lat));
  return poligono_m.map(([x, y]) => [
    centro.lat + y / metrosPorGrado,
    centro.lon + x / escala,
  ]);
}

/* Área en m² de un polígono lat/lon, proyectado al plano local. */
export function areaM2(poligonoLatLon) {
  if (poligonoLatLon.length < 3) { return 0; }
  const centro = centroDe(poligonoLatLon);
  const { poligono_m } = aMetros(poligonoLatLon, centro);
  let doble = 0;
  for (let i = 0; i < poligono_m.length; i += 1) {
    const [x1, y1] = poligono_m[i];
    const [x2, y2] = poligono_m[(i + 1) % poligono_m.length];
    doble += x1 * y2 - x2 * y1;
  }
  return Math.abs(doble) / 2;
}

/* ¿Se cruzan dos segmentos? (para detectar lotes con forma de moño). */
function cruzan(a, b, c, d) {
  const lado = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = lado(a, b, c);
  const d2 = lado(a, b, d);
  const d3 = lado(c, d, a);
  const d4 = lado(c, d, b);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

function autoIntersecta(poligono) {
  const n = poligono.length;
  for (let i = 0; i < n; i += 1) {
    const a = poligono[i];
    const b = poligono[(i + 1) % n];
    for (let j = i + 2; j < n; j += 1) {
      if (i === 0 && j === n - 1) { continue; } // lados contiguos
      const c = poligono[j];
      const d = poligono[(j + 1) % n];
      if (cruzan(a, b, c, d)) { return true; }
    }
  }
  return false;
}

/* Reglas mínimas para que una parcela sirva: 3–12 esquinas, cerca del ecuador
   habitable, sin dar la vuelta al mundo, con área y sin moños. */
export function validarParcela(poligonoLatLon) {
  if (!Array.isArray(poligonoLatLon) || poligonoLatLon.length === 0) {
    return { ok: false, motivo: 'sin_puntos' };
  }
  if (poligonoLatLon.length < 3) { return { ok: false, motivo: 'pocos_puntos' }; }
  if (poligonoLatLon.length > 12) { return { ok: false, motivo: 'demasiados_puntos' }; }
  if (poligonoLatLon.some(([lat]) => Math.abs(Number(lat)) > 85)) {
    return { ok: false, motivo: 'latitud' };
  }
  const lons = poligonoLatLon.map(([, lon]) => Number(lon));
  const lats = poligonoLatLon.map(([lat]) => Number(lat));
  if (Math.max(...lons) - Math.min(...lons) > 0.5
    || Math.max(...lats) - Math.min(...lats) > 0.5) {
    return { ok: false, motivo: 'extension' };
  }
  if (areaM2(poligonoLatLon) < 100) { return { ok: false, motivo: 'area' }; }
  if (autoIntersecta(poligonoLatLon)) { return { ok: false, motivo: 'auto_intersecta' }; }
  return { ok: true };
}

/* Lo que se copia al portapapeles y lee `tools/generar_usuarios.py`. */
export function paquete({ usuario, nombre, pin, parcelas, zoom = 17 }) {
  return {
    version: 1,
    zoom,
    usuario: { usuario, nombre, pin },
    parcelas: (parcelas || []).map((parcela) => ({
      nombre: parcela.nombre,
      cultivo: parcela.cultivo || 'por definir',
      poligono_latlon: parcela.poligono_latlon,
    })),
  };
}
