// Formatos de dinero y fechas de todo el frontend (mantenimiento fase 4).
// Antes había 9 copias repartidas en las pantallas; cada función reproduce EXACTAMENTE la que usaba
// cada pantalla, para que nada cambie a la vista (lo verifica tests/frontend_format_check.js).

const LOCALE = 'es-CO';

// ---------------------------------------------------------------- dinero

/** $1.234 — pesos sin decimales (Dashboard, Clientes, Alertas, Ajustes, POS, Caja). */
export const money = (v) => `$${Number(v || 0).toLocaleString(LOCALE, { maximumFractionDigits: 0 })}`;

/** $1.234,50 — con 2 decimales (Reportes). */
export const money2 = (v) => `$${Number(v || 0).toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const COP = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'COP', minimumFractionDigits: 0 });
/** $ 1.234 — formato de moneda COP de Intl (Fios, Facturas). */
export const currency = (amount) => COP.format(amount);

/** −$800 / +$300 / $0 — con signo (Ajustes de inventario). */
export const signedMoney = (v) => `${v < 0 ? '−' : v > 0 ? '+' : ''}$${Math.abs(Number(v || 0)).toLocaleString(LOCALE, { maximumFractionDigits: 0 })}`;

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
