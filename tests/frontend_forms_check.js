// Prueba de los formularios (mantenimiento fase 6): frontend/src/lib/validation.js y lib/schemas.js.
// - Las reglas de contraseña deben ser las mismas de backend/core/passwords.py (se leen de ese archivo).
// - Cada esquema: casos que deben pasar y casos que deben fallar con el mensaje exacto en el campo exacto.
//   node tests/frontend_forms_check.js
const path = require('path');
const fs = require('fs');
const Module = require('module');

const ROOT = path.join(__dirname, '..');
const FE = path.join(ROOT, 'frontend');
const SRC = path.join(FE, 'src');
const babel = require(path.join(FE, 'node_modules', '@babel', 'core'));
const presetEnv = require.resolve(path.join(FE, 'node_modules', '@babel', 'preset-env'));

// Carga un archivo de src/ con babel; resuelve '@/…' a src/ y los paquetes desde frontend/node_modules.
const cache = {};
function load(file) {
  const abs = path.resolve(file);
  if (cache[abs]) return cache[abs].exports;
  const { code } = babel.transformSync(fs.readFileSync(abs, 'utf8'), { filename: abs, presets: [[presetEnv, { targets: { node: 'current' } }]] });
  const m = new Module(abs);
  m.filename = abs;
  m.paths = Module._nodeModulePaths(FE);
  cache[abs] = m;
  m.require = (req) => {
    if (req.startsWith('@/') || req.startsWith('.')) {
      const base = req.startsWith('@/') ? path.join(SRC, req.slice(2)) : path.resolve(path.dirname(abs), req);
      const found = [base, `${base}.js`, `${base}.jsx`].find((f) => fs.existsSync(f) && fs.statSync(f).isFile());
      if (!found) throw new Error(`No se encontró ${req} (desde ${abs})`);
      return load(found);
    }
    return require(require.resolve(req, { paths: [FE] }));
  };
  m._compile(code, abs);
  return m.exports;
}

const V = load(path.join(SRC, 'lib', 'validation.js'));
const S = load(path.join(SRC, 'lib', 'schemas.js'));

let ok = 0; let fail = 0;
const check = (cond, label) => { if (cond) ok++; else { fail++; console.log(`FAIL ${label}`); } };

// ---------------------------------------------------------------- 1. contraseñas = backend
const py = fs.readFileSync(path.join(ROOT, 'backend', 'core', 'passwords.py'), 'utf8');
const pyMin = Number((py.match(/MIN_PASSWORD_LENGTH\s*=\s*(\d+)/) || [])[1]);
const pyInsecure = [...((py.match(/INSECURE_PASSWORDS\s*=\s*\{([^}]*)\}/) || [])[1] || '').matchAll(/"([^"]*)"/g)].map((x) => x[1]);
check(pyMin === V.MIN_PASSWORD_LENGTH, `largo mínimo de contraseña: backend ${pyMin}, frontend ${V.MIN_PASSWORD_LENGTH}`);
check(pyInsecure.length > 0 && [...pyInsecure].sort().join('|') === [...V.INSECURE_PASSWORDS].sort().join('|'),
  `contraseñas prohibidas distintas: backend ${pyInsecure}, frontend ${V.INSECURE_PASSWORDS}`);
for (const msg of ['La contraseña no puede estar vacía.', 'caracteres.', 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.']) {
  check(py.includes(msg.replace('caracteres.', 'caracteres."')), `mensaje del backend «${msg}»`);
}
const pw = [['', 'La contraseña no puede estar vacía.'], ['   ', 'La contraseña no puede estar vacía.'],
  ['corta12', `La contraseña debe tener al menos ${pyMin} caracteres.`], ['Admin123', 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.'],
  [' boltrex123 ', 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.'], ['Segura#2026', null], ['12345679', null]];
for (const [p, expected] of pw) check(V.passwordProblem(p) === expected, `passwordProblem(«${p}») = ${V.passwordProblem(p)}, esperado ${expected}`);

// ---------------------------------------------------------------- 2. correos
for (const e of ['a@b.co', 'nombre.apellido@empresa.com.co', ' x@y.com ']) check(V.isEmail(e), `correo válido «${e}»`);
for (const e of ['', 'a', 'a@b', 'a b@c.com', '@b.com', 'a@.com x']) check(!V.isEmail(e), `correo inválido «${e}»`);

// ---------------------------------------------------------------- 3. esquemas
// [esquema, datos, null si debe pasar | [campo, mensaje] si debe fallar]
const issues = (schema, data) => { const r = schema.safeParse(data); return r.success ? [] : r.error.issues; };
const expectOk = (name, schema, data) => {
  const errs = issues(schema, data);
  check(errs.length === 0, `${name}: debía pasar ${JSON.stringify(data)} → ${errs.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')}`);
};
const expectFail = (name, schema, data, field, message) => {
  const errs = issues(schema, data);
  const hit = errs.find((i) => i.path.join('.') === field);
  check(hit && hit.message === message, `${name}: «${field}» debía fallar con «${message}» → ${errs.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ') || 'pasó'}`);
};
const CASES = [];
const caseFor = (name, schema, base, fails = []) => CASES.push({ name, schema, base, fails });

caseFor('categoría', S.categorySchema, { name: 'Bebidas', description: '' }, [
  [{ name: '' }, 'name', 'El nombre de la categoría no puede estar vacío'],
  [{ name: '   ' }, 'name', 'El nombre de la categoría no puede estar vacío'],
]);
caseFor('lista de precios', S.priceListSchema, { name: 'mayorista', description: '', is_active: true }, [
  [{ name: ' ' }, 'name', 'El nombre de la lista de precios no puede estar vacío'],
]);
caseFor('forma de pago', S.paymentMethodSchema, { name: 'Nequi', description: 'x', is_active: false }, [
  [{ name: '' }, 'name', 'El nombre es requerido'],
]);
caseFor('motivo de ajuste', S.adjustmentReasonSchema, { name: 'Merma', description: '', applies_to: ['salida'], requires_note: false, is_active: true }, [
  [{ name: '' }, 'name', 'Escribe el nombre del motivo.'],
  [{ applies_to: [] }, 'applies_to', 'Marca al menos un tipo de ajuste (entrada, salida o conteo) para el motivo.'],
]);
caseFor('proveedor', S.supplierSchema, { name: 'Postobón', contact_name: '', phone: '', email: '', address: '' }, [
  [{ name: '' }, 'name', 'El nombre del proveedor no puede estar vacío'],
  [{ email: 'ventas@' }, 'email', 'El correo no es válido (ejemplo: nombre@dominio.com).'],
]);
check(issues(S.supplierSchema, { name: 'P', contact_name: '', phone: '', email: 'ventas@p.com', address: '' }).length === 0, 'proveedor con correo válido');

const USER = { first_name: 'Ana', last_name: 'Ruiz', email: 'ana@tienda.com', password: 'Segura#2026', phone: '', is_active: true };
caseFor('usuario nuevo', S.userCreateSchema, USER, [
  [{ first_name: ' ' }, 'first_name', 'Escribe los nombres.'],
  [{ last_name: '' }, 'last_name', 'Escribe los apellidos.'],
  [{ email: '' }, 'email', 'Escribe el correo.'],
  [{ email: 'ana@tienda' }, 'email', 'El correo no es válido (ejemplo: nombre@dominio.com).'],
  [{ password: '' }, 'password', 'La contraseña no puede estar vacía.'],
  [{ password: 'corta' }, 'password', 'La contraseña debe tener al menos 8 caracteres.'],
  [{ password: 'admin123' }, 'password', 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.'],
]);
caseFor('usuario editado', S.userEditSchema, { ...USER, password: '' }, [
  [{ password: 'corta' }, 'password', 'La contraseña debe tener al menos 8 caracteres.'],
  [{ password: 'Boltrex123' }, 'password', 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.'],
]);
check(issues(S.userEditSchema, { ...USER, password: '   ' }).length === 0, 'usuario editado: contraseña con solo espacios = no cambiarla (el backend la ignora)');

const TICKET = { company_name: 'Mi Tienda', nit: null, phone: '', email: null, address: '', ticket_width: 80, footer_message: 'Gracias', updated_at: '2026-01-01' };
caseFor('configuración del ticket', S.ticketConfigSchema, TICKET, [
  [{ company_name: '  ' }, 'company_name', 'El nombre de la empresa es requerido'],
  [{ company_name: null }, 'company_name', 'El nombre de la empresa es requerido'],
  [{ email: 'contacto' }, 'email', 'El correo no es válido (ejemplo: nombre@dominio.com).'],
  [{ ticket_width: 100 }, 'ticket_width', 'Elige el ancho del papel: 58 mm u 80 mm.'],
]);
check(issues(S.ticketConfigSchema, { ...TICKET, ticket_width: '58' }).length === 0, 'ticket: ancho 58 como texto');

// Productos: precios por lista (features/products/pricing.js).
const PRODUCT = { barcode: '770123', name: 'Gaseosa', description: '', category: 'Bebidas', purchase_price: '1000', tax_rate: '19', min_stock: '',
  prices: [{ price_list_name: 'default', price: '1500' }, { price_list_name: 'mayorista', price: '1200' }] };
caseFor('producto', S.productSchema, PRODUCT, [
  [{ barcode: '' }, 'barcode', 'Escribe el código de barras.'],
  [{ name: ' ' }, 'name', 'Escribe el nombre del producto.'],
  [{ category: '' }, 'category', 'Selecciona la categoría.'],
  [{ min_stock: '2.5' }, 'min_stock', 'El stock mínimo debe ser un número entero entre 0 y 1.000.000.'],
  [{ min_stock: '-1' }, 'min_stock', 'El stock mínimo debe ser un número entero entre 0 y 1.000.000.'],
  [{ purchase_price: '' }, 'purchase_price', 'El precio de compra debe ser un número.'],
  [{ purchase_price: '-5' }, 'purchase_price', 'El precio de compra no puede ser negativo.'],
  [{ tax_rate: '101' }, 'tax_rate', 'El IVA debe estar entre 0 y 100 %.'],
  [{ prices: [{ price_list_name: 'default', price: '0' }] }, 'prices.0.price', "El precio de la lista 'default' debe ser mayor a 0."],
  [{ prices: [{ price_list_name: 'default', price: '1500' }, { price_list_name: 'mayorista', price: '900' }] }, 'prices.1.price',
    "El precio de venta de la lista 'mayorista' no puede ser menor que el precio de compra."],
  [{ prices: [{ price_list_name: 'default', price: '1500' }, { price_list_name: 'default', price: '1600' }] }, 'prices.1.price_list_name',
    "La lista de precios 'default' está repetida."],
  [{ prices: [{ price_list_name: 'mayorista', price: '1500' }] }, 'prices.root',
    "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio."],
  [{ prices: [{ price_list_name: '', price: '' }] }, 'prices.root',
    "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'."],
]);
// Todos los errores a la vez: un campo vacío no esconde los errores de precios (withChecks).
{
  const errs = issues(S.productSchema, { ...PRODUCT, name: '', prices: [{ price_list_name: 'default', price: '10' }] }).map((i) => i.path.join('.'));
  check(errs.includes('name') && errs.includes('prices.0.price'), `producto: nombre vacío y precio bajo salen juntos → ${errs}`);
}

// Paridad: el primer problema de pricingIssues = lo que devolvía la función original (copiada tal cual).
const P = load(path.join(SRC, 'features', 'products', 'pricing.js'));
const origPricingProblem = ({ purchase_price, tax_rate, prices }) => {
  const cost = parseFloat(purchase_price);
  if (Number.isNaN(cost)) return 'El precio de compra debe ser un número.';
  if (cost < 0) return 'El precio de compra no puede ser negativo.';
  const iva = parseFloat(tax_rate);
  if (Number.isNaN(iva) || iva < 0 || iva > 100) return 'El IVA debe estar entre 0 y 100 %.';
  const rows = (prices || []).filter((p) => p.price_list_name || p.price !== '');
  if (rows.length === 0) return "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'.";
  const seen = new Set();
  for (const p of rows) {
    if (!p.price_list_name) return 'Cada precio de venta debe tener su lista de precios.';
    if (seen.has(p.price_list_name)) return `La lista de precios '${p.price_list_name}' está repetida.`;
    seen.add(p.price_list_name);
    const price = parseFloat(p.price);
    if (Number.isNaN(price) || price <= 0) return `El precio de la lista '${p.price_list_name}' debe ser mayor a 0.`;
    if (price < cost) return `El precio de venta de la lista '${p.price_list_name}' no puede ser menor que el precio de compra.`;
  }
  if (!seen.has('default')) {
    return "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio.";
  }
  return null;
};
{
  let seed = 6062026;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const NUMS = ['', '0', '-1', '1000', '999.99', '1500', 'abc', '2e3', ' 7 ', '100', '101', '19', '-0'];
  const LISTS = ['', 'default', 'default', 'mayorista', 'vip'];
  let same = 0; let diff = 0;
  for (let n = 0; n < 20000; n++) {
    const data = { purchase_price: pick(NUMS), tax_rate: pick(NUMS),
      prices: Array.from({ length: Math.floor(rnd() * 4) }, () => ({ price_list_name: pick(LISTS), price: pick(NUMS) })) };
    const a = P.pricingProblem(data); const b = origPricingProblem(data);
    if (a === b) same++; else { diff++; if (diff <= 3) console.log(`FAIL precios ${JSON.stringify(data)}\n  nuevo ${a}\n  antes ${b}`); }
  }
  check(diff === 0, `precios: ${diff} casos distintos de la versión original`);
  console.log(`precios: ${same} casos aleatorios idénticos a la versión original`);
}

const CLIENT = { document_type: 'CC', document_number: '123', first_name: 'Ana', last_name: 'Ruiz', phone: '', email: '', address: '',
  latitude: '', longitude: '', price_list: 'default', credit_days: '', credit_limit: '' };
caseFor('cliente', S.clientSchema, CLIENT, [
  [{ document_type: '' }, 'document_type', 'Selecciona el tipo de documento.'],
  [{ document_number: ' ' }, 'document_number', 'Escribe el número de documento.'],
  [{ first_name: '' }, 'first_name', 'Escribe los nombres.'],
  [{ email: 'ana' }, 'email', 'El correo no es válido (ejemplo: nombre@dominio.com).'],
  [{ latitude: '91' }, 'latitude', 'La latitud debe ser un número entre -90 y 90.'],
  [{ longitude: 'x' }, 'longitude', 'La longitud debe ser un número entre -180 y 180.'],
  [{ price_list: '' }, 'price_list', 'Elige la lista de precios.'],
  [{ credit_days: '1.5' }, 'credit_days', 'El plazo debe ser un número entero de días entre 0 y 3650.'],
  [{ credit_days: '3651' }, 'credit_days', 'El plazo debe ser un número entero de días entre 0 y 3650.'],
  [{ credit_limit: '-1' }, 'credit_limit', 'El cupo debe ser un valor de 0 o más.'],
]);
check(issues(S.clientSchema, { ...CLIENT, credit_days: 30, credit_limit: '500000', latitude: '4.6', longitude: '-74.08', email: null }).length === 0,
  'cliente con crédito (número del servidor) y coordenadas');
// El plazo máximo del frontend = el del backend.
check(/MAX_TERM_DAYS\s*=\s*3650\b/.test(fs.readFileSync(path.join(ROOT, 'backend', 'core', 'credit.py'), 'utf8')), 'plazo máximo 3650 = backend');

const PURCHASE = { supplier: { name: 'Postobón', contact_name: 'x' }, items: [{ barcode: '1', product_name: 'A', quantity: 2, unit_cost: '1000', total: 2000 }] };
caseFor('compra', S.purchaseSchema, PURCHASE, [
  [{ supplier: null }, 'supplier', 'Selecciona un proveedor'],
  [{ items: [] }, 'items', 'Agrega al menos un producto'],
  [{ items: [{ ...PURCHASE.items[0], quantity: '' }] }, 'items.0.quantity', 'La cantidad debe ser un número entero mayor a 0.'],
  [{ items: [{ ...PURCHASE.items[0], quantity: 0 }] }, 'items.0.quantity', 'La cantidad debe ser un número entero mayor a 0.'],
  [{ items: [{ ...PURCHASE.items[0], unit_cost: '-5' }] }, 'items.0.unit_cost', 'El costo unitario debe ser un número de 0 o más.'],
]);
check(issues(S.purchaseSchema, { ...PURCHASE, items: [{ ...PURCHASE.items[0], unit_cost: 0 }] }).length === 0, 'compra con costo 0 (regalo del proveedor)');

for (const { name, schema, base, fails } of CASES) {
  expectOk(name, schema, base);
  for (const [patch, field, message] of fails) expectFail(name, schema, { ...base, ...patch }, field, message);
}

// ---------------------------------------------------------------- 4. primer error para el aviso general
const rhfErrors = { name: { message: 'A', ref: { nodo: 'DOM' } }, prices: [undefined, { price: { message: 'B' } }] };
check(V.firstErrorMessage(rhfErrors) === 'A', 'firstErrorMessage toma el primero');
check(V.firstErrorMessage({ prices: [undefined, { price: { message: 'B', ref: {} } }] }) === 'B', 'firstErrorMessage entra en listas');
const cyclic = { ref: {} }; cyclic.ref.self = cyclic;
check(V.firstErrorMessage({ x: cyclic }) === null, 'firstErrorMessage no entra en ref (DOM)');

console.log(`${CASES.length} esquemas probados`);
console.log(`\n${fail ? 0 : 1}/1 pruebas OK  (${ok} verificaciones, ${fail} fallos)`);
process.exit(fail ? 1 : 0);
