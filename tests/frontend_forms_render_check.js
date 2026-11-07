// Prueba de los formularios RENDERIZADOS (mantenimiento fase 6), sin navegador: jsdom + React reales.
// Monta las pantallas de verdad (pages/*.js) con la API simulada y, como un usuario:
//   1. guarda con un dato malo → el error sale DEBAJO del campo, sale el aviso y NO se llama al servidor;
//   2. corrige el dato → el error desaparece;
//   3. guarda → lo que se envía al servidor tiene EXACTAMENTE el formato de antes de la fase 6.
//   node tests/frontend_forms_render_check.js
const path = require('path');
const fs = require('fs');
const Module = require('module');

const ROOT = path.join(__dirname, '..');
const FE = path.join(ROOT, 'frontend');
const SRC = path.join(FE, 'src');
const req = (name) => require(require.resolve(name, { paths: [FE] }));

// ---------------------------------------------------------------- navegador simulado (jsdom)
const { JSDOM } = req('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/', pretendToBeVisual: true });
const W = dom.window;
global.window = W; global.document = W.document; global.navigator = W.navigator;
for (const k of ['HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLFormElement', 'HTMLButtonElement', 'Element', 'Node', 'Event',
  'MouseEvent', 'KeyboardEvent', 'FocusEvent', 'PointerEvent', 'CustomEvent', 'MutationObserver', 'getComputedStyle', 'DocumentFragment',
  'requestAnimationFrame', 'cancelAnimationFrame', 'SVGElement', 'Text', 'NodeFilter', 'HTMLSelectElement', 'HTMLAnchorElement', 'DOMRect', 'Range']) {
  if (W[k] && global[k] === undefined) global[k] = typeof W[k] === 'function' && /^[a-z]/.test(k) ? W[k].bind(W) : W[k];
}
// Node ya trae Event/CustomEvent propios, que jsdom no acepta en dispatchEvent: se usan los de jsdom.
for (const k of ['Event', 'CustomEvent', 'EventTarget']) global[k] = W[k];
if (!W.PointerEvent) W.PointerEvent = class PointerEvent extends W.MouseEvent {};   // jsdom 16 no lo trae
class RO { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = RO; W.ResizeObserver = RO;
W.matchMedia = W.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
W.HTMLElement.prototype.scrollIntoView = function () {};
W.HTMLElement.prototype.hasPointerCapture = () => false;
W.HTMLElement.prototype.releasePointerCapture = () => {};
global.IS_REACT_ACT_ENVIRONMENT = true;
const realConsoleError = console.error;
console.error = (...a) => { const m = String(a[0] || ''); if (/not wrapped in act|DialogContent|Missing `Description`|aria-describedby/.test(m)) return; realConsoleError(...a); };

// ---------------------------------------------------------------- API, avisos y permisos simulados
const calls = [];          // { method, url, data }
const toasts = [];         // { kind, message }
let fixtures = {};         // url → data para GET (o función (params) → data)
let postFixtures = {};     // url → data que devuelve el POST
const respond = (url, params) => {
  const key = Object.keys(fixtures).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
  if (!key) return { data: { items: [], total: 0, page: 1, pages: 1 } };
  const value = typeof fixtures[key] === 'function' ? fixtures[key](params || {}) : fixtures[key];
  if (value instanceof Error) throw value;
  return { data: JSON.parse(JSON.stringify(value)) };
};
const apiMock = {
  API: '/api',
  api: {
    get: async (url, config) => respond(url, config && config.params),
    post: async (url, data) => {
      calls.push({ method: 'post', url, data });
      const key = Object.keys(postFixtures).find((k) => url.endsWith(k));
      return { data: key ? JSON.parse(JSON.stringify(postFixtures[key])) : {} };
    },
    put: async (url, data) => { calls.push({ method: 'put', url, data }); return { data: {} }; },
    delete: async (url) => { calls.push({ method: 'delete', url }); return { data: {} }; },
  },
  setAuthToken() {}, clearAuthToken() {},
};
const axiosMock = { get: async (url, config) => respond(url, config && config.params), post: apiMock.api.post, put: apiMock.api.put, delete: apiMock.api.delete,
  isAxiosError: () => false, defaults: { headers: { common: {} } } };
axiosMock.default = axiosMock;
const toastFn = (m) => toasts.push({ kind: 'info', message: m });
toastFn.error = (m) => toasts.push({ kind: 'error', message: m });
toastFn.success = (m) => toasts.push({ kind: 'success', message: m });
toastFn.info = toastFn; toastFn.warning = toastFn;
const React = req('react');
const MOCKS = {
  '@/api/client': apiMock,
  axios: axiosMock,
  sonner: { toast: toastFn, Toaster: () => null },
  '@/hooks/usePermissions': { usePermissions: () => ({ canCreate: () => true, canRead: () => true, canUpdate: () => true, canDelete: () => true, canAny: () => true, isAdmin: true }) },
  '@/components/ConfirmDialog': { useConfirm: () => async () => true, ConfirmProvider: ({ children }) => children },
  '@/auth/AuthProvider': { AuthContext: React.createContext({ user: { email: 'admin@boltrex.local', roles: ['admin'] } }) },
  '@/lib/events': { notifyDataChanged() {}, DATA_CHANGED: 'x', onDataChanged: () => () => {} },
};

// ---------------------------------------------------------------- carga de src/ con babel (JSX)
const babel = req('@babel/core');
const presets = [[require.resolve('@babel/preset-env', { paths: [FE] }), { targets: { node: 'current' } }],
  [require.resolve('@babel/preset-react', { paths: [FE] }), { runtime: 'automatic' }]];
const cache = {};
function load(abs) {
  if (cache[abs]) return cache[abs].exports;
  const { code } = babel.transformSync(fs.readFileSync(abs, 'utf8'), { filename: abs, presets, babelrc: false, configFile: false });
  const m = new Module(abs); m.filename = abs; m.paths = Module._nodeModulePaths(FE); cache[abs] = m;
  m.require = (r) => {
    if (MOCKS[r]) return MOCKS[r];
    if (r.startsWith('@/') || r.startsWith('.')) {
      const base = r.startsWith('@/') ? path.join(SRC, r.slice(2)) : path.resolve(path.dirname(abs), r);
      const found = [base, `${base}.js`, `${base}.jsx`, path.join(base, 'index.js')].find((f) => fs.existsSync(f) && fs.statSync(f).isFile());
      if (!found) throw new Error(`No se encontró ${r} (desde ${abs})`);
      if (/\.css$/.test(found)) return {};
      return load(found);
    }
    if (/\.css$/.test(r)) return {};
    return req(r);
  };
  m._compile(code, abs);
  return m.exports;
}
const page = (rel) => load(path.join(SRC, rel)).default;

// ---------------------------------------------------------------- utilidades de "usuario"
const { act } = React;
const { createRoot } = req('react-dom/client');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const settle = async (ms = 30) => { await act(async () => { await sleep(ms); }); };
const $ = (sel) => document.querySelector(sel);
const byTestId = (id) => $(`[data-testid="${id}"]`);
const must = (el, what) => { if (!el) throw new Error(`No se encontró ${what}`); return el; };
async function click(el) {
  await act(async () => {
    el.dispatchEvent(new W.PointerEvent('pointerdown', { bubbles: true, button: 0 }));
    el.dispatchEvent(new W.MouseEvent('mousedown', { bubbles: true, button: 0 }));
    el.dispatchEvent(new W.PointerEvent('pointerup', { bubbles: true, button: 0 }));
    el.dispatchEvent(new W.MouseEvent('mouseup', { bubbles: true, button: 0 }));
    el.dispatchEvent(new W.MouseEvent('click', { bubbles: true, button: 0 }));
  });
  await settle();
}
async function type(el, value) {
  const proto = el.tagName === 'TEXTAREA' ? W.HTMLTextAreaElement.prototype : W.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new W.Event('input', { bubbles: true }));
    el.dispatchEvent(new W.Event('change', { bubbles: true }));
  });
  await settle(10);
}
const errorText = (id) => { const el = document.getElementById(id); return el ? el.textContent : null; };

let root = null;
const RR = req('react-router-dom');
// route = { path: '/purchases/:purchaseNumber', url: '/purchases/PUR-000001' } para páginas con parámetros.
// Cualquier navegación fuera de esa ruta muestra <div data-testid="navigated-to" data-path="…">.
const Where = () => { const loc = RR.useLocation(); return React.createElement('div', { 'data-testid': 'navigated-to', 'data-path': loc.pathname }); };
async function mount(Component, data = {}, route = { path: '/', url: '/' }, posts = {}) {
  fixtures = data; postFixtures = posts; calls.length = 0; toasts.length = 0;
  if (root) await act(async () => root.unmount());
  document.body.innerHTML = '<div id="root"></div>';
  root = createRoot(document.getElementById('root'));
  const tree = React.createElement(RR.MemoryRouter, { initialEntries: [route.url] },
    React.createElement(RR.Routes, null,
      React.createElement(RR.Route, { path: route.path, element: React.createElement(Component) }),
      React.createElement(RR.Route, { path: '*', element: React.createElement(Where) })));
  await act(async () => root.render(tree));
  await settle(400);   // listas paginadas: espera de búsqueda (300 ms) + respuesta
}
const navigatedTo = () => { const el = byTestId('navigated-to'); return el ? el.getAttribute('data-path') : null; };
async function pressEnter(el) {
  await act(async () => { el.dispatchEvent(new W.KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); });
  await settle(30);
}
const stepper = (testId, sign) => { const input = must(byTestId(testId), testId); return sign > 0 ? input.nextElementSibling : input.previousElementSibling; };
const reset = () => { calls.length = 0; toasts.length = 0; };

let ok = 0; let fail = 0;
const check = (cond, label, extra = '') => { if (cond) ok++; else { fail++; console.log(`FAIL ${label}${extra ? `\n  ${extra}` : ''}`); } };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const lastToastError = () => [...toasts].reverse().find((t) => t.kind === 'error')?.message;

// ---------------------------------------------------------------- escenarios
const SCENARIOS = [];
const scenario = (name, fn) => SCENARIOS.push({ name, fn });

scenario('Categorías: nombre vacío → error debajo; corregido → POST igual que antes', async () => {
  await mount(page('pages/Categories.js'));
  await click(must(byTestId('create-category-button'), 'botón Nueva Categoría'));
  await click(must(byTestId('save-category-button'), 'botón Crear'));
  check(errorText('name-error') === 'El nombre de la categoría no puede estar vacío', 'categoría: error debajo del nombre', `→ ${errorText('name-error')}`);
  check(lastToastError() === 'El nombre de la categoría no puede estar vacío', 'categoría: además el aviso de siempre');
  check(calls.length === 0, 'categoría: con error no se llama al servidor');
  await type(byTestId('category-name-input'), 'Bebidas');
  check(errorText('name-error') === null, 'categoría: al escribir, el error desaparece');
  await click(byTestId('save-category-button'));
  check(calls.length === 1 && calls[0].method === 'post' && calls[0].url === '/categories' && same(calls[0].data, { name: 'Bebidas', description: '' }),
    'categoría: POST /categories con el formato de antes', JSON.stringify(calls));
});

scenario('Usuarios: contraseña obvia → error debajo; editar sin contraseña → PUT', async () => {
  await mount(page('pages/UsersManagement.js'), {
    '/rbac/roles': [],
    '/rbac/users': { items: [{ email: 'ana@tienda.com', first_name: 'Ana', last_name: 'Ruiz', phone: '', is_active: true, roles: [] }], total: 1, page: 1, pages: 1 },
  });
  await click(must(byTestId('create-user-button'), 'botón Nuevo Usuario'));
  await type(byTestId('user-first-name-input'), 'Luis');
  await type(byTestId('user-last-name-input'), 'Gómez');
  await type(byTestId('user-email-input'), 'luis@tienda');
  await type(byTestId('user-password-input'), 'admin123');
  await click(byTestId('save-user-button'));
  check(errorText('email-error') === 'El correo no es válido (ejemplo: nombre@dominio.com).', 'usuario: error debajo del correo', `→ ${errorText('email-error')}`);
  check(errorText('password-error') === 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.', 'usuario: error debajo de la contraseña', `→ ${errorText('password-error')}`);
  check(calls.length === 0, 'usuario: con errores no se llama al servidor');
  await type(byTestId('user-email-input'), 'luis@tienda.com');
  await type(byTestId('user-password-input'), 'Segura#2026');
  check(errorText('password-error') === null && errorText('email-error') === null, 'usuario: corregidos, los errores desaparecen');
  await click(byTestId('save-user-button'));
  check(calls.length === 1 && calls[0].url === '/rbac/users' && same(calls[0].data,
    { email: 'luis@tienda.com', password: 'Segura#2026', first_name: 'Luis', last_name: 'Gómez', phone: '', is_active: true }),
    'usuario: POST /rbac/users con el formato de antes', JSON.stringify(calls));
  // Editar: contraseña vacía = no cambiarla (válido).
  reset();
  await click(must(byTestId('edit-user-0'), 'botón editar usuario'));
  await click(byTestId('save-user-button'));
  check(calls.length === 1 && calls[0].method === 'put' && calls[0].url === '/rbac/users/ana@tienda.com' && same(calls[0].data,
    { email: 'ana@tienda.com', password: '', first_name: 'Ana', last_name: 'Ruiz', phone: '', is_active: true }),
    'usuario editado sin contraseña: PUT con el formato de antes', JSON.stringify(calls));
});

const PRODUCT = { barcode: '770123', name: 'Gaseosa', description: '', category: 'Bebidas', purchase_price: 1000, tax_rate: 19, stock: 5, min_stock: null,
  prices: [{ price_list_name: 'default', price: 1500 }, { price_list_name: 'mayorista', price: 1200 }] };
scenario('Productos: precio menor que el costo → error en esa fila; corregido → PUT igual que antes', async () => {
  await mount(page('pages/Products.js'), {
    '/categories': [{ name: 'Bebidas' }],
    '/price-lists': [{ name: 'default', is_active: true }, { name: 'mayorista', is_active: true }],
    '/products': { items: [PRODUCT], total: 1, page: 1, pages: 1 },
  });
  await click(must(byTestId('edit-product-0'), 'botón editar producto'));
  await type(must(byTestId('price-input-1'), 'precio fila 1'), '900');
  await type(byTestId('product-name-input'), '  ');
  await click(byTestId('save-product-button'));
  check(errorText('price-error-1') === "El precio de venta de la lista 'mayorista' no puede ser menor que el precio de compra.",
    'producto: error debajo de la fila de precio', `→ ${errorText('price-error-1')}`);
  check(errorText('name-error') === 'Escribe el nombre del producto.', 'producto: error del nombre al mismo tiempo', `→ ${errorText('name-error')}`);
  check(calls.length === 0, 'producto: con errores no se llama al servidor');
  await type(byTestId('price-input-1'), '1300');
  check(errorText('price-error-1') === null, 'producto: al corregir el precio, su error desaparece');
  await type(byTestId('product-name-input'), 'Gaseosa 400 ml');
  // Subir el costo por encima de un precio revalida las filas (deps).
  await type(byTestId('product-purchase-price-input'), '1400');
  check(errorText('price-error-1') === "El precio de venta de la lista 'mayorista' no puede ser menor que el precio de compra.",
    'producto: subir el costo revalida los precios', `→ ${errorText('price-error-1')}`);
  await type(byTestId('product-purchase-price-input'), '1000');
  await click(byTestId('save-product-button'));
  check(calls.length === 1 && calls[0].method === 'put' && calls[0].url === '/products/770123' && same(calls[0].data, {
    barcode: '770123', name: 'Gaseosa 400 ml', description: '', category: 'Bebidas', purchase_price: 1000, tax_rate: 19, min_stock: null,
    prices: [{ price_list_name: 'default', price: 1500 }, { price_list_name: 'mayorista', price: 1300 }],
  }), 'producto: PUT con el formato de antes', JSON.stringify(calls));
});

const CLIENT = { document_type: 'CC', document_number: '123', first_name: 'Ana', last_name: 'Ruiz', phone: '300', email: 'ana@x.com', address: '',
  latitude: 4.6, longitude: null, price_list: 'default', credit_days: null, credit_limit: 0 };
scenario('Clientes: plazo decimal → error debajo; corregido → PUT igual que antes', async () => {
  await mount(page('pages/Clients.js'), {
    '/document-types': [{ code: 'CC', name: 'Cédula' }],
    '/price-lists': [{ name: 'default', is_active: true }],
    '/clients': { items: [CLIENT], total: 1, page: 1, pages: 1 },
  });
  await click(must(byTestId('edit-client-0'), 'botón editar cliente'));
  await type(byTestId('client-credit-days-input'), '1.5');
  await type(byTestId('client-email-input'), 'ana@');
  await click(byTestId('save-client-button'));
  check(errorText('credit_days-error') === 'El plazo debe ser un número entero de días entre 0 y 3650.', 'cliente: error debajo del plazo', `→ ${errorText('credit_days-error')}`);
  check(errorText('email-error') === 'El correo no es válido (ejemplo: nombre@dominio.com).', 'cliente: error debajo del correo');
  check(calls.length === 0, 'cliente: con errores no se llama al servidor');
  await type(byTestId('client-credit-days-input'), '30');
  await type(byTestId('client-email-input'), 'ana@x.com');
  await click(byTestId('save-client-button'));
  const sent = calls[0] && calls[0].data;
  check(calls.length === 1 && calls[0].method === 'put' && calls[0].url === '/clients/123' && same(sent, {
    document_type: 'CC', document_number: '123', first_name: 'Ana', last_name: 'Ruiz', phone: '300', email: 'ana@x.com', address: '',
    latitude: 4.6, longitude: null, price_list: 'default', credit_days: 30, credit_limit: null,
  }), 'cliente: PUT con el formato de antes', JSON.stringify(calls));
});

const GAS = { barcode: '770123', name: 'Gaseosa', purchase_price: 1200, stock: 8, prices: [{ price_list_name: 'default', price: 1500 }] };
const PAN = { barcode: '770999', name: 'Pan', purchase_price: 500, stock: 0, prices: [{ price_list_name: 'default', price: 800 }] };
const page1 = (items) => ({ items, total: items.length, page: 1, pages: 1 });
const PURCHASE_FIXTURES = {
  '/suppliers': (params) => page1(params.search ? [{ name: 'Postobón', contact_name: 'Juan Pérez', phone: '300 111 2233' }] : []),
  '/products': (params) => page1(params.barcode ? [GAS, PAN].filter((p) => p.barcode === params.barcode)
    : params.search ? [GAS, PAN].filter((p) => `${p.name} ${p.barcode}`.toLowerCase().includes(params.search.toLowerCase())) : []),
};
const EDITOR = { path: '/purchases/nueva', url: '/purchases/nueva' };

scenario('Compras (página nueva): proveedor, lector con Enter, − / +, costo antes/ahora, stock → POST igual que antes', async () => {
  await mount(page('pages/PurchaseEditor.js'), PURCHASE_FIXTURES, EDITOR, { '/purchases': { purchase_number: 'PUR-000010' } });
  check(!byTestId('save-purchase-button'), 'compra nueva: sin productos no hay botones de guardar');
  await type(must(byTestId('supplier-search-input'), 'buscador de proveedor'), 'Pos');
  await settle(400);
  await click(must(byTestId('purchase-supplier-0'), 'proveedor encontrado'));
  check(document.body.textContent.includes('Juan Pérez') && byTestId('supplier-search-input') === null, 'compra: proveedor elegido (tarjeta verde con contacto)');
  const search = must(byTestId('product-search-input'), 'buscador de productos');
  await type(search, '770123');
  await pressEnter(search);
  await settle(50);
  check(byTestId('purchase-item-0') && byTestId('item-quantity-770123').value === '1', 'lector: Enter con el código agrega 1 unidad');
  check(search.value === '', 'lector: el buscador queda vacío para el siguiente');
  await type(search, '770123');
  await pressEnter(search);
  await settle(50);
  check(byTestId('item-quantity-770123').value === '2', 'lector: el mismo código otra vez suma 1');
  await type(search, '77012');
  await pressEnter(search);
  await settle(50);
  check(lastToastError() === 'No hay un producto con el código «77012».' && !byTestId('purchase-item-1'),
    'lector: un código parcial NO agrega otro producto', lastToastError());
  await type(search, 'Pan');
  await settle(400);
  check(document.body.textContent.includes('Costo actual · Stock: 0'), 'búsqueda: muestra costo actual y stock');
  await click(must(byTestId('purchase-product-0'), 'producto Pan en la lista'));
  await click(stepper('item-quantity-770999', +1));
  check(byTestId('item-quantity-770999').value === '2', 'compra: botón + suma');
  await click(stepper('item-quantity-770999', -1));
  await click(stepper('item-quantity-770999', -1));
  check(byTestId('item-quantity-770999').value === '1', 'compra: botón − no baja de 1');
  await click(stepper('item-quantity-770999', +1));
  await type(byTestId('item-cost-770123'), '1300');
  check((byTestId('cost-change-770123') || {}).textContent === 'antes $1.200', 'compra: costo nuevo vs. antes', (byTestId('cost-change-770123') || {}).textContent);
  check(byTestId('item-stock-770123').textContent === '8 → 10', 'compra: stock actual → después', byTestId('item-stock-770123').textContent);
  check(byTestId('purchase-total').textContent === '$3.600' && byTestId('purchase-units').textContent === '2 / 4', 'compra: total y unidades',
    `${byTestId('purchase-total').textContent} ${byTestId('purchase-units').textContent}`);
  await click(byTestId('save-purchase-button'));
  await settle(50);
  check(calls.length === 1 && calls[0].method === 'post' && calls[0].url === '/purchases' && same(calls[0].data, {
    supplier_name: 'Postobón', items: [{ barcode: '770123', product_name: 'Gaseosa', quantity: 2, unit_cost: 1300, total: 2600 },
      { barcode: '770999', product_name: 'Pan', quantity: 2, unit_cost: 500, total: 1000 }],
  }), 'compra: POST /purchases con el formato de antes', JSON.stringify(calls));
  check(navigatedTo() === '/purchases', 'compra: al guardar vuelve al listado', navigatedTo());
});

scenario('Compras: «Guardar y procesar» → guarda, procesa y avisa costos y precios bajo el costo', async () => {
  await mount(page('pages/PurchaseEditor.js'), PURCHASE_FIXTURES, EDITOR, {
    '/purchases': { purchase_number: 'PUR-000009' },
    '/purchases/PUR-000009/confirm': { cost_changes: [{ barcode: '770123', name: 'Gaseosa', old_cost: 1200, new_cost: 1600 }],
      price_warnings: [{ barcode: '770123', name: 'Gaseosa', new_cost: 1600, prices: [{ price_list_name: 'default', price: 1500 }] }] },
  });
  await type(byTestId('supplier-search-input'), 'Pos');
  await settle(400);
  await click(byTestId('purchase-supplier-0'));
  await type(byTestId('product-search-input'), '770123');
  await pressEnter(byTestId('product-search-input'));
  await settle(50);
  await type(byTestId('item-cost-770123'), '1600');
  await click(byTestId('save-and-process-purchase-button'));
  await settle(80);
  check(calls.map((c) => `${c.method} ${c.url}`).join(' | ') === 'post /purchases | post /purchases/PUR-000009/confirm',
    'guardar y procesar: crea el borrador y lo procesa', JSON.stringify(calls));
  const msgs = toasts.map((t) => `${t.kind}: ${t.message}`).join('\n');
  check(msgs.includes('success: Compra PUR-000009 procesada: inventario actualizado'), 'procesar: aviso de éxito', msgs);
  check(msgs.includes('Costo actualizado: Gaseosa $1.200 → $1.600'), 'procesar: avisa el costo actualizado', msgs);
  check(msgs.includes('Precio de venta por debajo del costo nuevo: Gaseosa (costo $1.600; default $1.500)'), 'procesar: avisa el precio a revisar', msgs);
  check(navigatedTo() === '/purchases', 'procesar: vuelve al listado');
});

scenario('Compras: editar borrador → error en la fila; corregido → PUT igual que antes; confirmada = solo lectura', async () => {
  const purchase = { purchase_number: 'COM-000001', supplier_name: 'Postobón', status: 'borrador', total: 2000, created_by: 'admin@boltrex.com',
    created_at: '2026-11-01T10:00:00Z', items: [{ barcode: '770123', product_name: 'Gaseosa', quantity: 2, unit_cost: 1000, total: 2000 }] };
  await mount(page('pages/PurchaseEditor.js'), { ...PURCHASE_FIXTURES, '/purchases/COM-000001': purchase, '/products/770123': GAS },
    { path: '/purchases/:purchaseNumber', url: '/purchases/COM-000001' });
  check(byTestId('item-stock-770123').textContent === '8 → 10' && (byTestId('cost-change-770123') || {}).textContent === 'antes $1.200',
    'editar: trae stock y costo actuales del producto');
  await type(must(byTestId('item-cost-770123'), 'costo de la fila'), '-5');
  await click(byTestId('save-purchase-button'));
  check(errorText('item-error-770123') === 'El costo unitario debe ser un número de 0 o más.', 'compra: error debajo de la fila', `→ ${errorText('item-error-770123')}`);
  check(calls.length === 0, 'compra: con errores no se llama al servidor');
  await type(byTestId('item-cost-770123'), '1100');
  check(errorText('item-error-770123') === null, 'compra: al corregir, el error desaparece');
  await type(byTestId('item-quantity-770123'), '3');
  await click(byTestId('save-purchase-button'));
  await settle(50);
  check(calls.length === 1 && calls[0].method === 'put' && calls[0].url === '/purchases/COM-000001' && same(calls[0].data, {
    supplier_name: 'Postobón', items: [{ barcode: '770123', product_name: 'Gaseosa', quantity: 3, unit_cost: 1100, total: 3300 }],
  }), 'compra: PUT con el formato de antes', JSON.stringify(calls));

  await mount(page('pages/PurchaseEditor.js'), { ...PURCHASE_FIXTURES, '/purchases/COM-000001': purchase, '/products/770123': GAS },
    { path: '/purchases/:purchaseNumber', url: '/purchases/COM-000001' });
  await click(must([...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Cambiar Proveedor'), 'botón Cambiar Proveedor'));
  check(byTestId('save-purchase-button').disabled && byTestId('save-and-process-purchase-button').disabled,
    'compra: sin proveedor los botones de guardar quedan deshabilitados (como antes)');

  await mount(page('pages/PurchaseEditor.js'), { '/purchases/COM-000001': { ...purchase, status: 'confirmado' }, '/products/770123': GAS },
    { path: '/purchases/:purchaseNumber', url: '/purchases/COM-000001' });
  check(!byTestId('product-search-input') && !byTestId('save-purchase-button') && !byTestId('item-cost-770123')
    && document.body.textContent.includes('Compra COM-000001'), 'compra confirmada: solo lectura');
});

scenario('POS: lector con Enter agrega al carrito; el código parcial no; − / + con el stock del producto', async () => {
  const client = { document_type: 'CC', document_number: '123', first_name: 'Ana', last_name: 'Ruiz', price_list: 'default' };
  await mount(page('pages/POS.js'), {
    '/payment-methods/active': [{ name: 'Efectivo' }], '/cash/settings': { require_open_session: false }, '/cash/current': { session: null },
    '/clients': (params) => page1(params.search ? [client] : []),
    '/credit/client-status': { balance: 0, overdue_balance: 0, term_days: 7 },
    '/products': PURCHASE_FIXTURES['/products'],
  }, { path: '/', url: '/' });
  await type(must(byTestId('pos-search-client-input'), 'buscador de clientes'), 'Ana');
  await settle(400);
  await click(must(byTestId('pos-client-0'), 'cliente encontrado'));
  const search = must(byTestId('pos-search-product-input'), 'buscador de productos del POS');
  await type(search, '770123');
  await pressEnter(search);
  await settle(50);
  check(byTestId('cart-item-0') && byTestId('cart-quantity-input-770123').value === '1' && search.value === '', 'POS lector: Enter agrega 1 y limpia el buscador');
  await type(search, '770123');
  await pressEnter(search);
  await settle(50);
  check(byTestId('cart-quantity-input-770123').value === '2', 'POS lector: el mismo código suma 1');
  await type(search, '7701');
  await pressEnter(search);
  await settle(50);
  check(lastToastError() === 'No hay un producto con el código «7701».' && !byTestId('cart-item-1'), 'POS lector: código parcial no agrega nada');
  await click(stepper('cart-quantity-input-770123', +1));
  check(byTestId('cart-quantity-input-770123').value === '3', 'POS: + funciona con el producto escaneado (usa su stock)');
});

scenario('Tickets: nombre de empresa vacío → error debajo; corregido → PUT igual que antes', async () => {
  const config = { company_name: 'Mi Tienda', nit: null, phone: '', email: '', address: '', ticket_width: 80, footer_message: 'Gracias' };
  await mount(page('pages/TicketConfig.js'), { '/ticket-config': config });
  await type(must(byTestId('input-company-name'), 'nombre de empresa'), '');
  check(byTestId('ticket-preview').textContent.includes('NOMBRE EMPRESA'), 'ticket: la vista previa sigue lo que se escribe');
  await click(byTestId('save-config-btn'));
  check(errorText('company_name-error') === 'El nombre de la empresa es requerido', 'ticket: error debajo del nombre', `→ ${errorText('company_name-error')}`);
  check(calls.length === 0, 'ticket: con error no se llama al servidor');
  await type(byTestId('input-company-name'), 'Tienda Don Pepe');
  await click(byTestId('save-config-btn'));
  check(calls.length === 1 && calls[0].url === '/ticket-config' && same(calls[0].data, { ...config, company_name: 'Tienda Don Pepe' }),
    'ticket: PUT con el formato de antes', JSON.stringify(calls));
});

scenario('Motivos de ajuste: sin tipos → error debajo; con tipo → POST', async () => {
  await mount(page('pages/AdjustmentReasons.js'));
  await click(must(byTestId('create-reason-button'), 'botón Nuevo Motivo'));
  await type(byTestId('reason-name-input'), 'Merma');
  await click(byTestId('reason-kind-salida'));   // venía marcado: se desmarca → ninguno
  await click(byTestId('save-reason-button'));
  check(errorText('reason-kinds-error') === 'Marca al menos un tipo de ajuste (entrada, salida o conteo) para el motivo.', 'motivo: error debajo de los tipos', `→ ${errorText('reason-kinds-error')}`);
  check(calls.length === 0, 'motivo: con error no se llama al servidor');
  await click(byTestId('reason-kind-conteo'));
  check(errorText('reason-kinds-error') === null, 'motivo: al marcar uno, el error desaparece');
  await click(byTestId('save-reason-button'));
  check(calls.length === 1 && same(calls[0].data, { name: 'Merma', description: '', applies_to: ['conteo'], requires_note: false, is_active: true }),
    'motivo: POST con el formato de antes', JSON.stringify(calls));
});

scenario('Proveedores: correo inválido → error debajo; corregido → POST', async () => {
  await mount(page('pages/Suppliers.js'));
  await click(must(byTestId('create-supplier-button'), 'botón Nuevo Proveedor'));
  await type(byTestId('supplier-name-input'), 'Postobón');
  await type(byTestId('supplier-email-input'), 'ventas@');
  await click(byTestId('save-supplier-button'));
  check(errorText('email-error') === 'El correo no es válido (ejemplo: nombre@dominio.com).', 'proveedor: error debajo del correo', `→ ${errorText('email-error')}`);
  check(calls.length === 0, 'proveedor: con error no se llama al servidor');
  await type(byTestId('supplier-email-input'), '');
  await click(byTestId('save-supplier-button'));
  check(calls.length === 1 && same(calls[0].data, { name: 'Postobón', contact_name: '', phone: '', email: '', address: '' }),
    'proveedor: correo vacío se acepta; POST con el formato de antes', JSON.stringify(calls));
});

scenario('Formas de pago y listas de precios: nombre vacío → error; con nombre → POST', async () => {
  await mount(page('pages/PaymentMethods.js'));
  await click(must(byTestId('create-payment-method-btn'), 'botón Nueva Forma de Pago'));
  await click(byTestId('save-payment-method-btn'));
  check(errorText('name-error') === 'El nombre es requerido', 'forma de pago: error debajo del nombre', `→ ${errorText('name-error')}`);
  await type(byTestId('input-payment-method-name'), 'Nequi');
  await click(byTestId('switch-payment-method-status'));
  await click(byTestId('save-payment-method-btn'));
  check(calls.length === 1 && same(calls[0].data, { name: 'Nequi', description: '', is_active: false }),
    'forma de pago: POST con el formato de antes (interruptor apagado)', JSON.stringify(calls));

  await mount(page('pages/PriceLists.js'));
  await click(must(byTestId('create-price-list-button'), 'botón Nueva Lista'));
  await type(byTestId('price-list-name-input'), '   ');
  await click(byTestId('save-price-list-button'));
  check(errorText('name-error') === 'El nombre de la lista de precios no puede estar vacío', 'lista de precios: error debajo del nombre', `→ ${errorText('name-error')}`);
  await type(byTestId('price-list-name-input'), 'mayorista');
  await click(byTestId('save-price-list-button'));
  check(calls.length === 1 && same(calls[0].data, { name: 'mayorista', description: '', is_active: true }),
    'lista de precios: POST con el formato de antes', JSON.stringify(calls));
});

(async () => {
  for (const { name, fn } of SCENARIOS) {
    const before = fail;
    try { await fn(); } catch (e) {
      fail++;
      const inner = e.errors ? e.errors.map((x) => (x && x.stack ? x.stack.split('\n').slice(0, 4).join(' | ') : String(x))).join(' || ') : '';
      console.log(`FAIL ${name}: ${e.stack.split('\n').slice(0, 3).join(' | ')}${inner ? `\n  ${inner}` : ''}`);
    }
    console.log(`${fail === before ? '✓' : '✗'} ${name}`);
  }
  if (root) await act(async () => root.unmount());
  console.log(`\n${fail ? 0 : 1}/1 pruebas OK  (${SCENARIOS.length} pantallas, ${ok} verificaciones, ${fail} fallos)`);
  process.exit(fail ? 1 : 0);
})();
