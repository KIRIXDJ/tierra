/* Lenguaje de campo: traduce unidades técnicas a frases que un agricultor
   entiende sin estudiar el dato. Cada función devuelve texto plano; la
   interfaz decide dónde va. Sin DOM: se prueba con Node (tests/lenguaje.mjs).

   Regla: nunca inventa una cifra. Solo explica la que ya viene de los datos. */

const fmt = (valor, decimales = 0) => Number(valor).toFixed(decimales).replace('.', ',');
const miles = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');

/* 1 mm de lluvia = 1 litro por metro cuadrado. Es la equivalencia que se usa
   en el campo; el número redondeado se lee mejor de lejos. */
export function lluvia(mm) {
  if (mm === null || mm === undefined || Number.isNaN(Number(mm))) { return 'sin dato'; }
  const litros = Math.round(Number(mm));
  return `${litros} L por m²`;
}

export function comparacionLluvia(pct) {
  if (pct === null || pct === undefined || Number.isNaN(Number(pct))) { return 'sin normal'; }
  const valor = Math.round(Number(pct));
  if (valor === 0) { return 'igual que su normal'; }
  return `${valor > 0 ? '+' : ''}${valor} % sobre su normal`;
}

export function lluviaHora(mmHora) {
  if (mmHora === null || mmHora === undefined) { return 'sin dato'; }
  const valor = Number(mmHora);
  if (!Number.isFinite(valor) || valor <= 0.05) { return 'no está lloviendo'; }
  return `cae ${fmt(valor, 1)} L por m² por hora`;
}

/* NDVI 0–1: cuánto verde hay. 1 = vegetación densa, 0 = suelo o planta seca. */
export function verde(ndvi) {
  if (ndvi === null || ndvi === undefined || Number.isNaN(Number(ndvi))) { return 'sin dato'; }
  const puntos = Math.round(Number(ndvi) * 100);
  return `verde ${puntos} de 100`;
}

/* Evapotranspiración: el agua que el cultivo y el suelo se llevan al día. */
export function aguaQueGasta(mmDia) {
  if (mmDia === null || mmDia === undefined || Number.isNaN(Number(mmDia))) { return 'sin dato'; }
  return `el cultivo gasta ${fmt(Number(mmDia), 1)} L por m² al día`;
}

export function estadoHumedad(pct) {
  if (pct === null || pct === undefined) { return 'sin lectura'; }
  const valor = Number(pct);
  if (!Number.isFinite(valor)) { return 'sin lectura'; }
  if (valor < 25) { return 'seco · hay que regar'; }
  if (valor < 40) { return 'regular'; }
  return 'con agua';
}

export function diasSecos(dias) {
  if (dias === null || dias === undefined || Number.isNaN(Number(dias))) { return 'sin dato'; }
  return `${Math.round(Number(dias))} días sin lluvia al año`;
}

export function puntaje(nota) {
  if (nota === null || nota === undefined || Number.isNaN(Number(nota))) { return 'sin dato'; }
  return `puntaje ${Math.round(Number(nota))}/100`;
}

/* Hectáreas para quien no maneja el término: se da también el área en m². */
export function superficieHa(ha) {
  const valor = Number(ha);
  if (!Number.isFinite(valor)) { return 'sin dato'; }
  const metros = Math.round(valor * 10000);
  return `${fmt(valor, 2)} ha · ${miles(metros)} m²`;
}

export function areaM2(ha) {
  const valor = Number(ha);
  if (!Number.isFinite(valor)) { return 'sin dato'; }
  return `${miles(Math.round(valor * 10000))} m²`;
}

export function pendiente(grados) {
  const valor = Number(grados);
  if (!Number.isFinite(valor)) { return 'sin dato'; }
  const como = valor < 5 ? 'casi plano' : valor < 15 ? 'algo inclinado' : 'inclinado';
  return `${como} (${fmt(valor, 1)}°)`;
}

/* Humedad del suelo en fracción 0–1 (POWER) o porcentaje 0–100. */
export function aguaSuelo(valor, enFraccion = true) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) { return 'sin dato'; }
  const puntos = enFraccion ? Math.round(numero * 100) : Math.round(numero);
  return `${puntos} de 100`;
}

export function aguaEnSuelo(valor, enFraccion = true) {
  const corto = aguaSuelo(valor, enFraccion);
  return corto === 'sin dato' ? corto : `agua en el suelo: ${corto}`;
}

export function temperatura(grados) {
  const valor = Number(grados);
  if (!Number.isFinite(valor)) { return 'sin dato'; }
  return `${fmt(valor, 1)} °C`;
}

export const GLOSARIO = [
  ['L por m² (mm)', 'Un milímetro de lluvia es un litro de agua por metro cuadrado. '
    + 'Si llovió 127 L por m², el suelo recibió 127 litros en cada metro.'],
  ['Verde (NDVI)', 'Qué tanta vegetación hay, de 0 a 100. Cuanto más alto, más verde '
    + 'y más cubierto el suelo; no dice si la planta está sana por dentro.'],
  ['Agua del suelo', 'Cuánta agua tiene el suelo, de 0 a 100. Bajo 25 está seco y '
    + 'conviene regar; el riego automático de la demo usa ese umbral.'],
  ['Lo que gasta el cultivo', 'Agua que se evapora y que la planta consume al día, '
    + 'en litros por metro cuadrado. No es lo que hay que regar: depende de la lluvia.'],
  ['Días sin lluvia', 'Días del año en que no llovió lo suficiente. Sirve para saber '
    + 'cuánto aguanta el cultivo sin riego en la temporada seca.'],
  ['Reanálisis', 'Datos de un modelo alimentado con observaciones, no de un '
    + 'termómetro en tu parcela. Por eso se avisa en pantalla.'],
  ['Puntaje de rotación', 'De 0 a 100: reparte el riesgo de sequía entre cultivos '
    + 'y suma diversidad. Orienta la conversación con el agrónomo, no la reemplaza.'],
  ['Hectárea', '10.000 m². La app da también el área en m² para quien no usa la palabra.'],
];
