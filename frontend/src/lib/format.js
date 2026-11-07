// Formatos de dinero, números y fechas de TODO el frontend (fase 4; regla única desde «formato-numeros-colombia»).
// Regla del sistema (la misma de backend/core/money.py; ambas se prueban con tests/money_cases.json):
//   punto de miles y coma decimal · centavos SOLO si existen · signo menos «−».
//   1500 → $1.500 · 999.99 → $999,99 · -1500 → −$1.500 · números: 2.5 → 2,5 · 12345 → 12.345
// Se arma a mano (no con toLocaleString): así da lo mismo en cualquier navegador e idioma del equipo
// (con 'es-ES', por ejemplo, 1234 sale «1234» sin punto). No formatear números ni fechas en las pantallas:
// usar estas funciones (tests/frontend_format_check.js revisa que no queden formatos sueltos).

const LOCALE = 'es-CO';
const MINUS = '−';

// Redondeo a centavos, mitad hacia arriba (igual que el backend).
const round2 = (value) => {
  const v = Number(value || 0);
  if (!Number.isFinite(v)) return 0;
  const r = Math.floor(Math.abs(v) * 100 + 0.5) / 100;
  return v < 0 && r !== 0 ? -r : r;
};
const group = (integer) => String(integer).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const split = (a) => {
  const cents = Math.round(a * 100);
  return [Math.floor(cents / 100), cents % 100];
};

// ---------------------------------------------------------------- dinero y números

/** $1.500 · $999,99 · −$1.500 · $0 — todo el dinero del sistema. */
export const money = (value) => {
  const n = round2(value);
  const [whole, cents] = split(Math.abs(n));
  return `${n < 0 ? MINUS : ''}$${group(whole)}${cents ? `,${String(cents).padStart(2, '0')}` : ''}`;
};

/** Antes eran otras variantes (2 decimales siempre en Reportes; moneda COP de Intl en Fios y Facturas). Hoy = money. */
export const money2 = money;
export const currency = money;

/** +$300 · −$800 · $0 — diferencias (sobrantes/faltantes, ajustes de inventario). */
export const signedMoney = (value) => {
  const n = round2(value);
  return `${n > 0 ? '+' : ''}${money(n)}`;
};

/** 12.345 · 2,5 · 0,33 · −4 — cantidades y porcentajes (hasta 2 decimales, sin ceros de sobra). */
export const number = (value) => {
  const n = round2(value);
  const [whole, cents] = split(Math.abs(n));
  const decimals = cents ? String(cents).padStart(2, '0').replace(/0+$/, '') : '';
  return `${n < 0 ? MINUS : ''}${group(whole)}${decimals ? `,${decimals}` : ''}`;
};

/** 19 % · 8,5 % */
export const percent = (value) => `${number(value)} %`;

/** $1,5 M · $12 mil · $800 — montos cortos para los ejes de las gráficas. */
export const compactMoney = (value) => {
  const n = Number(value || 0);
  if (n >= 1e6) return `$${number(Math.round(n / 1e5) / 10)} M`;
  if (n >= 1e3) return `$${number(Math.round(n / 1e3))} mil`;
  return money(Math.round(n));
};

/** Fecha local AAAA-MM-DD (para enviar filtros de fecha al servidor, no para mostrar). */
export const localYmd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// ---------------------------------------------------------------- fechas

/** 06/11/2026, 09:30 a. m. — fecha y hora (Fios, Facturas). 'N/A' si no hay fecha. */
export const dateTime = (value) => {
  if (!value) return 'N/A';
  try {
    return new Date(value).toLocaleDateString(LOCALE, {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return value;
  }
};

/** 06/11/2026, 09:30:15 a. m. — con segundos (Auditoría). '' si no hay fecha. */
export const dateTimeSeconds = (iso) => {
  if (!iso) return '';
  return new Date(iso).toLocaleString(LOCALE, {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
};

/** 6/11/26, 9:30 a. m. — corta (Caja). '—' si no hay fecha. */
export const shortDateTime = (iso) => (iso ? new Date(iso).toLocaleString(LOCALE, { dateStyle: 'short', timeStyle: 'short' }) : '—');

/** 6/11/2026 — solo fecha (Fios: vencimientos). '—' si no hay fecha. */
export const shortDate = (value) => (value ? new Date(value).toLocaleDateString(LOCALE) : '—');

/** 2026-11-06 → 06/11/2026 (fechas AAAA-MM-DD de los formularios). '' si viene vacío. */
export const ymdToDmy = (s) => (s ? s.split('-').reverse().join('/') : '');
