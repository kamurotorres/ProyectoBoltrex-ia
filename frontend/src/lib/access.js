// Mapa único de secciones y permisos (backlog P1.13).
//
// Lo usan el menú lateral (Layout), las rutas protegidas (App) y la pantalla de inicio.
// Cada sección declara el permiso que exige para VERLA; los botones de cada pantalla
// usan `can(user, módulo, acción)` para crear / editar / eliminar.
// Debe coincidir con lo que exige el backend (core/permissions.py): el backend es la
// seguridad real; esto es para que la pantalla sea coherente con lo que se puede hacer.
//
// Módulo puro (sin React) para poder probarlo con node: tests/frontend_access_check.js.

export const ADMIN_ROLE = 'Administrador';

// path: ruta · label: nombre en el menú · icon: nombre del icono (Layout lo traduce)
// module: slug RBAC que debe tener `read` (o `modules`: basta `read` en cualquiera de ellos,
//   igual que require_any_permission del backend) · adminOnly: solo el rol Administrador
// actions: la pantalla tiene acciones de crear/editar/eliminar → si el rol solo puede ver,
//   se muestra el aviso "Solo lectura"
// group / subgroup: dónde va en el menú (rama menu-por-grupos; ver MENU_GROUPS). El ORDEN de esta lista es
//   el del menú: lo más usado en el día primero (vender, después comprar) y la configuración al final.
export const SECTIONS = [
  { path: '/', label: 'Dashboard', icon: 'LayoutDashboard', module: 'dashboard', group: 'inicio' },
  // Ventas
  { path: '/pos', label: 'POS', icon: 'ShoppingCart', module: 'pos', actions: true, group: 'ventas' },
  { path: '/cash', label: 'Caja', icon: 'Banknote', module: 'cash', actions: true, group: 'ventas' },
  { path: '/invoices', label: 'Facturas', icon: 'Receipt', module: 'invoices', group: 'ventas' },
  { path: '/fios', label: 'Fios (Créditos)', icon: 'Wallet', module: 'fios', actions: true, group: 'ventas' },
  { path: '/returns', label: 'Devoluciones', icon: 'RotateCcw', module: 'returns', actions: true, group: 'ventas' },
  { path: '/clients', label: 'Clientes', icon: 'Users', module: 'clients', actions: true, group: 'ventas' },
  // Compras e inventario
  { path: '/purchases', label: 'Compras', icon: 'ShoppingBag', module: 'purchases', actions: true, group: 'compras' },
  { path: '/inventory', label: 'Inventario', icon: 'Warehouse', module: 'inventory', group: 'compras' },
  { path: '/products', label: 'Productos', icon: 'Package', module: 'products', actions: true, group: 'compras' },
  { path: '/suppliers', label: 'Proveedores', icon: 'Truck', module: 'suppliers', actions: true, group: 'compras' },
  // Informes
  { path: '/reports', label: 'Reportes', icon: 'FileText', module: 'reports', group: 'informes' },
  // Configuración · catálogos
  { path: '/categories', label: 'Categorías', icon: 'FolderOpen', module: 'categories', actions: true, group: 'config', subgroup: 'Catálogos' },
  { path: '/price-lists', label: 'Listas de Precios', icon: 'DollarSign', module: 'price-lists', actions: true, group: 'config', subgroup: 'Catálogos' },
  { path: '/payment-methods', label: 'Formas de Pago', icon: 'CreditCard', module: 'payment-methods', actions: true, group: 'config', subgroup: 'Catálogos' },
  { path: '/adjustment-reasons', label: 'Motivos de Ajuste', icon: 'SlidersHorizontal', module: 'adjustment-reasons', actions: true, group: 'config', subgroup: 'Catálogos' },
  // Configuración · sistema
  { path: '/users', label: 'Usuarios', icon: 'UserCog', module: 'users', actions: true, group: 'config', subgroup: 'Sistema' },
  { path: '/roles', label: 'Roles y Permisos', icon: 'Shield', modules: ['permissions', 'roles'], actions: true, group: 'config', subgroup: 'Sistema' },
  { path: '/ticket-config', label: 'Config. Tickets', icon: 'Ticket', module: 'ticket-config', actions: true, group: 'config', subgroup: 'Sistema' },
  // El factory reset lo exige el backend al rol Administrador: la sección también.
  { path: '/settings', label: 'Config. Sistema', icon: 'Settings', adminOnly: true, group: 'config', subgroup: 'Sistema' },
  { path: '/import', label: 'Importar', icon: 'Upload', module: 'import', actions: true, group: 'config', subgroup: 'Sistema' },
  { path: '/audit', label: 'Auditoría', icon: 'ScrollText', adminOnly: true, group: 'config', subgroup: 'Sistema' },
];

// Grupos del menú, en orden. label null = sin título (Dashboard). collapsible: se puede plegar.
export const MENU_GROUPS = [
  { key: 'inicio', label: null },
  { key: 'ventas', label: 'Ventas' },
  { key: 'compras', label: 'Compras e inventario' },
  { key: 'informes', label: 'Informes' },
  { key: 'config', label: 'Configuración', collapsible: true },
];

export const isAdmin = (user) => Boolean(user && (user.roles || []).includes(ADMIN_ROLE));

/** ¿El usuario tiene `action` (read/create/update/delete) sobre `module`? */
export const can = (user, module, action = 'read') =>
  Boolean(user && user.permissions && user.permissions[module] && user.permissions[module][action] === true);

/** ¿Tiene al menos uno de los pares [módulo, acción]? (igual que require_any_permission del backend) */
export const canAny = (user, ...pairs) => pairs.some(([module, action]) => can(user, module, action));

export const findSection = (path) => {
  const clean = (path || '/').replace(/\/+$/, '') || '/';
  return SECTIONS.find((s) => s.path === clean) || null;
};

export const canAccessSection = (user, section) => {
  if (!section || !user) return false;
  if (section.adminOnly) return isAdmin(user);
  return sectionModules(section).some((m) => can(user, m, 'read'));
};

export const sectionModules = (section) => (section ? section.modules || (section.module ? [section.module] : []) : []);

/** Puede ver la sección pero no crear, editar ni eliminar nada en ella. */
export const isReadOnly = (user, section) =>
  Boolean(section && section.actions && !isAdmin(user) && canAccessSection(user, section) &&
    !sectionModules(section).some((m) => ['create', 'update', 'delete'].some((a) => can(user, m, a))));

export const allowedSections = (user) => SECTIONS.filter((s) => canAccessSection(user, s));

/** Menú del usuario: solo los grupos con alguna sección que puede ver (sin títulos vacíos).
 *  [{ key, label, collapsible, sections, subgroups: [{ label, sections }] }] */
export const menuGroups = (user) => {
  const allowed = allowedSections(user);
  return MENU_GROUPS.map((g) => {
    const sections = allowed.filter((s) => s.group === g.key);
    const subgroups = [];
    sections.forEach((s) => {
      const label = s.subgroup || null;
      let sg = subgroups.find((x) => x.label === label);
      if (!sg) { sg = { label, sections: [] }; subgroups.push(sg); }
      sg.sections.push(s);
    });
    return { ...g, sections, subgroups };
  }).filter((g) => g.sections.length > 0);
};

// Orden de preferencia para la pantalla de inicio; después, el orden del menú.
const HOME_PRIORITY = ['/', '/pos'];

/** Pantalla de inicio: Dashboard si puede verlo; si no, POS (cajeros); si no, su primera sección. */
export const homePath = (user) => {
  const allowed = allowedSections(user).map((s) => s.path);
  const preferred = HOME_PRIORITY.find((p) => allowed.includes(p));
  return preferred || allowed[0] || null;
};
