// Pruebas del mapa de secciones y permisos del frontend (backlog P1.13). Sin navegador:
//
//     node tests/frontend_access_check.js
//
// Carga frontend/src/lib/access.js (transpilado con el Babel que ya trae el frontend) y
// comprueba que menú, rutas y backend estén sincronizados y que las reglas de acceso,
// pantalla de inicio y "solo lectura" se comporten como se acordó.
const fs = require('fs');
const path = require('path');
const Module = require('module');

const ROOT = path.resolve(__dirname, '..');
const FE = path.join(ROOT, 'frontend');
const babel = require(path.join(FE, 'node_modules', '@babel', 'core'));

const results = [];
const check = (name, ok, detail = '') => {
  results.push(Boolean(ok));
  console.log(`${ok ? 'OK ' : 'FAIL'} ${name}${ok ? '' : ` -> ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`}`);
};

function load(file) {
  const src = fs.readFileSync(file, 'utf8');
  const { code } = babel.transformSync(src, {
    filename: file, babelrc: false, configFile: false,
    plugins: [path.join(FE, 'node_modules', '@babel', 'plugin-transform-modules-commonjs')],
  });
  const m = new Module(file);
  m._compile(code, file);
  return m.exports;
}

const A = load(path.join(FE, 'src', 'lib', 'access.js'));
const appSrc = fs.readFileSync(path.join(FE, 'src', 'App.js'), 'utf8');
const layoutSrc = fs.readFileSync(path.join(FE, 'src', 'components', 'Layout.js'), 'utf8');
const rbacSrc = fs.readFileSync(path.join(ROOT, 'backend', 'rbac.py'), 'utf8');

// --- 1. Sincronía menú / rutas / backend ---
const pagesBlock = appSrc.slice(appSrc.indexOf('const PAGES = {'), appSrc.indexOf('};', appSrc.indexOf('const PAGES = {')));
const pagePaths = [...pagesBlock.matchAll(/'(\/[a-z-]+)':/g)].map((m) => m[1]);
const sectionPaths = A.SECTIONS.map((s) => s.path);
check('rutas sin duplicados', new Set(sectionPaths).size === sectionPaths.length, sectionPaths);
check('toda sección del menú (menos "/") tiene pantalla en App.js',
  sectionPaths.filter((p) => p !== '/').every((p) => pagePaths.includes(p)),
  sectionPaths.filter((p) => p !== '/' && !pagePaths.includes(p)));
check('toda pantalla de App.js está en el mapa (ninguna ruta sin proteger)',
  pagePaths.every((p) => sectionPaths.includes(p)), pagePaths.filter((p) => !sectionPaths.includes(p)));
check('las rutas de App.js se generan desde el mapa con RequireSection',
  /Object\.entries\(PAGES\)\.map/.test(appSrc) && /<RequireSection path=\{path\}>/.test(appSrc));
check('ninguna <Route path="..."> suelta fuera del mapa (salvo login, cambio de contraseña y comodín)',
  [...appSrc.matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => m[1]).every((p) => ['/login', '/', '*'].includes(p)),
  [...appSrc.matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => m[1]));
check('el inicio "/" pasa por HomeRoute', /<Route index element=\{<HomeRoute>/.test(appSrc));
check('el menú usa el mapa (sin lista propia)', /allowedSections\(user\)/.test(layoutSrc) && !/moduleSlug:/.test(layoutSrc));
const backendSlugs = [...rbacSrc.matchAll(/"slug":\s*"([a-z-]+)"/g)].map((m) => m[1]);
const used = A.SECTIONS.flatMap((s) => A.sectionModules(s));
check('todo módulo del mapa existe en el backend (rbac.DEFAULT_MODULES)', used.every((m) => backendSlugs.includes(m)),
  used.filter((m) => !backendSlugs.includes(m)));
check('todo icono del mapa existe en Layout', A.SECTIONS.every((s) => new RegExp(`\\b${s.icon}\\b`).test(layoutSrc.split('const ICONS')[1] || '')),
  A.SECTIONS.filter((s) => !new RegExp(`\\b${s.icon}\\b`).test(layoutSrc.split('const ICONS')[1] || '')).map((s) => s.icon));

// --- 2. Reglas de acceso ---
const perms = (map) => Object.fromEntries(Object.entries(map).map(([m, acts]) => [m, {
  read: acts.includes('r'), create: acts.includes('c'), update: acts.includes('u'), delete: acts.includes('d') }]));
const allPerms = perms(Object.fromEntries(backendSlugs.map((s) => [s, 'rcud'])));
const admin = { roles: ['Administrador'], permissions: allPerms };
const gestor = { roles: ['Gestor'], permissions: allPerms };                    // todos los permisos, sin rol Administrador
const cajero = { roles: ['Cajero'], permissions: perms({ pos: 'rc', clients: 'r', products: 'r' }) };
const lector = { roles: ['Consulta'], permissions: perms({ dashboard: 'r', products: 'r', invoices: 'r' }) };
const rolesOnly = { roles: ['RRHH'], permissions: perms({ roles: 'rc' }) };
const nadie = { roles: [], permissions: {} };
const sec = A.findSection;

check('admin ve todas las secciones', A.allowedSections(admin).length === A.SECTIONS.length);
check('Auditoría y Config. Sistema: solo Administrador (aunque tenga todos los permisos)',
  !A.canAccessSection(gestor, sec('/audit')) && !A.canAccessSection(gestor, sec('/settings')) &&
  A.canAccessSection(admin, sec('/audit')) && A.canAccessSection(admin, sec('/settings')));
check('cajero: solo POS, clientes y productos',
  JSON.stringify(A.allowedSections(cajero).map((s) => s.path)) === JSON.stringify(['/products', '/clients', '/pos']),
  A.allowedSections(cajero).map((s) => s.path));
check('cajero no entra a Usuarios por URL', !A.canAccessSection(cajero, sec('/users')));
check('inicio del cajero (sin Dashboard) → POS', A.homePath(cajero) === '/pos', A.homePath(cajero));
const bodega = { roles: ['Bodega'], permissions: perms({ inventory: 'r', purchases: 'rcu' }) };
check('inicio sin Dashboard ni POS → su primera sección del menú', A.homePath(bodega) === '/purchases', A.homePath(bodega));
check('inicio con Dashboard → "/"', A.homePath(lector) === '/');
check('sin permisos → sin pantalla de inicio', A.homePath(nadie) === null && A.allowedSections(nadie).length === 0);
check('Roles y Permisos con solo el permiso "roles" (como el backend)', A.canAccessSection(rolesOnly, sec('/roles')));
check('ruta inexistente → sin acceso', A.findSection('/no-existe') === null && !A.canAccessSection(admin, null));
check('ruta con barra final se reconoce', A.findSection('/products/') && A.findSection('/products/').path === '/products');
check('usuario nulo no ve nada', A.allowedSections(null).length === 0 && !A.can(null, 'products'));

// --- 3. Solo lectura ---
check('lector en Productos → solo lectura', A.isReadOnly(lector, sec('/products')));
check('lector en Facturas (pantalla sin acciones) → sin aviso', !A.isReadOnly(lector, sec('/invoices')));
check('cajero en POS (puede crear) → sin aviso', !A.isReadOnly(cajero, sec('/pos')));
check('cajero en Clientes (solo ver) → solo lectura', A.isReadOnly(cajero, sec('/clients')));
check('admin nunca ve "solo lectura"', A.SECTIONS.every((s) => !A.isReadOnly(admin, s)));
check('sin acceso → no aplica "solo lectura"', !A.isReadOnly(cajero, sec('/users')));
check('canAny como require_any_permission', A.canAny(rolesOnly, ['permissions', 'create'], ['roles', 'create']) &&
  !A.canAny(cajero, ['permissions', 'create'], ['roles', 'create']));

console.log(`\n${results.filter(Boolean).length}/${results.length} pruebas OK`);
process.exit(results.every(Boolean) ? 0 : 1);
