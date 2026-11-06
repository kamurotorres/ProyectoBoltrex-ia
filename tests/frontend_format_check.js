// Prueba de frontend/src/lib/format.js (mantenimiento fase 4): cada función debe dar EXACTAMENTE lo mismo que
// la copia que tenía cada pantalla antes de unificarlas (las originales están copiadas aquí tal cual).
//   node tests/frontend_format_check.js
const path = require('path');
const fs = require('fs');
const Module = require('module');

const FE = path.join(__dirname, '..', 'frontend');
const babel = require(path.join(FE, 'node_modules', '@babel', 'core'));
const src = fs.readFileSync(path.join(FE, 'src', 'lib', 'format.js'), 'utf8');
const { code } = babel.transformSync(src, {
  filename: 'format.js',
  presets: [[require.resolve(path.join(FE, 'node_modules', '@babel', 'preset-env')), { targets: { node: 'current' } }]],
});
const m = new Module('format.js');
m._compile(code, 'format.js');
const f = m.exports;

// ---- Originales (copiados de las pantallas antes de la fase 4) ----
const orig = {
  money_clients: (v) => `$${Number(v || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 })}`,          // Clients, AlertsBell, Adjustments, POS money0
  money_charts: (v) => '$' + Number(v || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 }),           // Charts (Dashboard)
  money_cash: (v) => '$' + Math.round(Number(v || 0)).toLocaleString('es-CO'),                                // Cash
  money_reports: (v) => '$' + Number(v || 0).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  currency: (amount) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0 }).format(amount),
  signed: (v) => `${v < 0 ? '−' : v > 0 ? '+' : ''}$${Math.abs(Number(v || 0)).toLocaleString('es-CO', { maximumFractionDigits: 0 })}`,
  dateTime: (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleDateString('es-CO', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    } catch { return dateStr; }
  },
  audit: (iso) => { if (!iso) return ''; return new Date(iso).toLocaleString('es-CO', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }); },
  when: (iso) => (iso ? new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—'),
  shortDate: (dateStr) => (dateStr ? new Date(dateStr).toLocaleDateString('es-CO') : '—'),
  dmy: (s) => (s ? s.split('-').reverse().join('/') : ''),
};

const NUMS = [0, 1, 7, 999, 1000, 1234, 1234.4, 1234.5, 1234.56, 1234.999, 18000, 1250000, 987654321.12, -1, -800, -1234.5, -0.4,
  '1500', '', null, undefined, NaN];
const DATES = [null, '', '2026-11-06T14:30:15Z', '2026-01-01T00:00:00+00:00', '2026-12-31T23:59:59.999Z', new Date(2026, 4, 9, 7, 5, 3).toISOString()];
const YMD = ['', null, '2026-11-06', '2026-01-31'];

let ok = 0; let fail = 0;
const same = (label, newFn, oldFn, values) => {
  const bad = values.filter((v) => newFn(v) !== oldFn(v));
  if (bad.length) { fail++; console.log(`FAIL ${label}: ${bad.map((v) => `${JSON.stringify(v)} → nuevo ${JSON.stringify(newFn(v))} / antes ${JSON.stringify(oldFn(v))}`).join(' · ')}`); }
  else { ok++; console.log(`OK   ${label} (${values.length} valores)`); }
};

same('money = Clientes/Alertas/Ajustes/POS', f.money, orig.money_clients, NUMS);
same('money = Dashboard (gráficas)', f.money, orig.money_charts, NUMS);
// Caja usaba Math.round: igual salvo negativos terminados exactamente en ,5 (redondeo hacia arriba vs. hacia afuera).
same('money = Caja (sin negativos ,5)', f.money, orig.money_cash, NUMS.filter((v) => !(typeof v === 'number' && v < 0 && Math.abs(v % 1) === 0.5)));
same('money2 = Reportes', f.money2, orig.money_reports, NUMS);
same('currency = Fios/Facturas', f.currency, orig.currency, NUMS.filter((v) => v !== undefined));
same('signedMoney = Ajustes', f.signedMoney, orig.signed, NUMS);
same('dateTime = Fios/Facturas', f.dateTime, orig.dateTime, DATES);
same('dateTimeSeconds = Auditoría', f.dateTimeSeconds, orig.audit, DATES);
same('shortDateTime = Caja', f.shortDateTime, orig.when, DATES);
same('shortDate = Fios', f.shortDate, orig.shortDate, DATES);
same('ymdToDmy = POS', f.ymdToDmy, orig.dmy, YMD);
const spot = [[f.money(1234567), '$1.234.567'], [f.money2(1234.5), '$1.234,50'], [f.signedMoney(-800), '−$800'], [f.ymdToDmy('2026-11-06'), '06/11/2026']];
spot.forEach(([got, want]) => { if (got === want) ok++; else { fail++; console.log(`FAIL ejemplo: ${got} ≠ ${want}`); } });
console.log(`\n${ok}/${ok + fail} pruebas OK`);
process.exit(fail ? 1 : 0);
