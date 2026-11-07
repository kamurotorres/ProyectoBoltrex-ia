// Prueba de frontend/src/lib/format.js. Dinero/números: la regla única del sistema (tests/money_cases.json, la
// misma tabla del backend). Fechas: EXACTAMENTE lo mismo que las copias que tenía cada pantalla (fase 4).
// Además: ninguna pantalla formatea números o fechas por su cuenta.
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

const DATES = [null, '', '2026-11-06T14:30:15Z', '2026-01-01T00:00:00+00:00', '2026-12-31T23:59:59.999Z', new Date(2026, 4, 9, 7, 5, 3).toISOString()];
const YMD = ['', null, '2026-11-06', '2026-01-31'];

let ok = 0; let fail = 0;
const same = (label, newFn, oldFn, values) => {
  const bad = values.filter((v) => newFn(v) !== oldFn(v));
  if (bad.length) { fail++; console.log(`FAIL ${label}: ${bad.map((v) => `${JSON.stringify(v)} → nuevo ${JSON.stringify(newFn(v))} / antes ${JSON.stringify(oldFn(v))}`).join(' · ')}`); }
  else { ok++; console.log(`OK   ${label} (${values.length} valores)`); }
};

// ---- Dinero y números: regla única del sistema = la misma tabla que prueba el backend (tests/unit/test_money.py).
const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, 'money_cases.json'), 'utf8'));
for (const [key, fn] of [['money', f.money], ['signed_money', f.signedMoney], ['number', f.number]]) {
  const bad = CASES[key].filter(([v, want]) => fn(v) !== want);
  if (bad.length) { fail++; console.log(`FAIL ${key} ≠ backend: ${bad.map(([v, want]) => `${JSON.stringify(v)} → ${JSON.stringify(fn(v))} (esperado ${want})`).join(' · ')}`); }
  else { ok++; console.log(`OK   ${key} = backend/core/money.py (${CASES[key].length} casos)`); }
}
const spot = [[f.money2(1234.5), '$1.234,50'], [f.currency(1500), '$1.500'], [f.percent(8.5), '8,5 %'], [f.money(undefined), '$0'],
  [f.money(NaN), '$0'], [f.ymdToDmy('2026-11-06'), '06/11/2026']];
spot.forEach(([got, want]) => { if (got === want) ok++; else { fail++; console.log(`FAIL ejemplo: ${got} ≠ ${want}`); } });

// ---- Fechas: iguales a las de antes.
same('dateTime = Fios/Facturas', f.dateTime, orig.dateTime, DATES);
same('dateTimeSeconds = Auditoría', f.dateTimeSeconds, orig.audit, DATES);
same('shortDateTime = Caja', f.shortDateTime, orig.when, DATES);
same('shortDate = Fios', f.shortDate, orig.shortDate, DATES);
same('ymdToDmy = POS', f.ymdToDmy, orig.dmy, YMD);

// ---- Nadie formatea por su cuenta: números y fechas solo con lib/format.js.
const LOOSE = /\.toLocale(Date|Time)?String\(|Intl\.(NumberFormat|DateTimeFormat)|\.toFixed\(/;
const loose = [];
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).forEach((e) => {
  const full = path.join(dir, e.name);
  if (e.isDirectory()) { if (!['ui', 'node_modules'].includes(e.name)) walk(full); return; }
  if (!/\.jsx?$/.test(e.name) || full.endsWith(path.join('lib', 'format.js'))) return;
  fs.readFileSync(full, 'utf8').split('\n').forEach((line, i) => {
    if (LOOSE.test(line)) loose.push(`${path.relative(path.join(__dirname, '..'), full)}:${i + 1}: ${line.trim().slice(0, 110)}`);
  });
});
walk(path.join(__dirname, '..', 'frontend', 'src'));
if (loose.length) { fail++; console.log(`FAIL formatos sueltos (usar money/number/percent/dateTime… de @/lib/format):\n  ${loose.join('\n  ')}`); }
else { ok++; console.log('OK   sin formatos de números/fechas sueltos en las pantallas'); }

console.log(`\n${ok}/${ok + fail} pruebas OK`);
process.exit(fail ? 1 : 0);
