// Prueba de frontend/src/features/pos/cart.js (mantenimiento fase 5): las reglas del carrito deben dar
// EXACTAMENTE lo mismo que el código original de pages/POS.js (copiado abajo tal cual, adaptado solo para
// recibir el estado como parámetro en vez de leerlo del componente). Escenarios aleatorios con semilla fija.
//   node tests/frontend_cart_check.js
const path = require('path');
const fs = require('fs');
const Module = require('module');

const FE = path.join(__dirname, '..', 'frontend');
const babel = require(path.join(FE, 'node_modules', '@babel', 'core'));
const load = (rel) => {
  const { code } = babel.transformSync(fs.readFileSync(path.join(FE, 'src', rel), 'utf8'), {
    filename: rel, presets: [[require.resolve(path.join(FE, 'node_modules', '@babel', 'preset-env')), { targets: { node: 'current' } }]],
  });
  const m = new Module(rel); m._compile(code, rel); return m.exports;
};
const C = load('features/pos/cart.js');

// ---------------- ORIGINAL (pages/POS.js antes de la fase 5) ----------------
const orig = {
  getProductPrice(product, selectedClient) {
    const prices = product.prices || [];
    const pick = (name) => prices.find((p) => p.price_list_name === name);
    const found = (selectedClient && pick(selectedClient.price_list)) || pick('default');
    return found ? found.price : null;
  },
  addToCart(cart, product, selectedClient) {
    let error = null; let next = cart;
    if (!selectedClient) return { cart, error: 'Primero selecciona un cliente' };
    if (orig.getProductPrice(product, selectedClient) === null) return { cart, error: `El producto '${product.name}' no tiene precio de venta. Agrégale un precio en Productos.` };
    if (product.stock <= 0) return { cart, error: 'Producto sin stock' };
    const existingItemIndex = cart.findIndex(item => item.barcode === product.barcode);
    if (existingItemIndex !== -1) {
      const existingItem = cart[existingItemIndex];
      const newQuantity = existingItem.quantity + 1;
      if (newQuantity > product.stock) return { cart, error: 'Stock insuficiente' };
      const subtotal = existingItem.unit_price * newQuantity;
      const taxAmount = (subtotal * existingItem.tax_rate) / 100;
      const total = subtotal + taxAmount;
      next = cart.map((item, index) => index === existingItemIndex ? { ...item, quantity: newQuantity, subtotal, tax_amount: taxAmount, total } : item);
    } else {
      const unitPrice = orig.getProductPrice(product, selectedClient);
      const subtotal = unitPrice;
      const taxAmount = (subtotal * product.tax_rate) / 100;
      const total = subtotal + taxAmount;
      next = [...cart, { barcode: product.barcode, product_name: product.name, quantity: 1, unit_price: unitPrice, tax_rate: product.tax_rate, subtotal, tax_amount: taxAmount, total }];
    }
    return { cart: next, error };
  },
  updateQuantity(cart, barcode, delta, products) {
    let error = null;
    const product = products.find(p => p.barcode === barcode);
    const next = cart.map(item => {
      if (item.barcode === barcode) {
        const newQuantity = item.quantity + delta;
        if (newQuantity <= 0) return item;
        if (newQuantity > product.stock) { error = 'Stock insuficiente'; return item; }
        const subtotal = item.unit_price * newQuantity;
        const taxAmount = (subtotal * item.tax_rate) / 100;
        const total = subtotal + taxAmount;
        return { ...item, quantity: newQuantity, subtotal, tax_amount: taxAmount, total };
      }
      return item;
    });
    return { cart: next, error };
  },
  setQuantity(cart, barcode, value, products) {
    const product = products.find(p => p.barcode === barcode);
    const qty = parseInt(value) || 0;
    if (qty <= 0) return { cart, error: null };
    if (product && qty > product.stock) return { cart, error: 'Stock insuficiente' };
    return { cart: cart.map(item => {
      if (item.barcode === barcode) {
        const subtotal = item.unit_price * qty;
        const taxAmount = (subtotal * item.tax_rate) / 100;
        const total = subtotal + taxAmount;
        return { ...item, quantity: qty, subtotal, tax_amount: taxAmount, total };
      }
      return item;
    }), error: null };
  },
  reprice(cart, products, client) {
    return cart.map(item => {
      const product = products.find(p => p.barcode === item.barcode);
      if (product) {
        const prices = product.prices || [];
        const found = prices.find(p => p.price_list_name === client.price_list) || prices.find(p => p.price_list_name === 'default');
        const unitPrice = found ? found.price : item.unit_price;
        const subtotal = unitPrice * item.quantity;
        const taxAmount = (subtotal * item.tax_rate) / 100;
        const total = subtotal + taxAmount;
        return { ...item, unit_price: unitPrice, subtotal, tax_amount: taxAmount, total };
      }
      return item;
    });
  },
  totals(cart) {
    const subtotal = cart.reduce((sum, item) => sum + item.subtotal, 0);
    const totalTax = cart.reduce((sum, item) => sum + item.tax_amount, 0);
    const total = cart.reduce((sum, item) => sum + item.total, 0);
    return { subtotal, totalTax, total };
  },
};

// ---------------- escenarios aleatorios (semilla fija) ----------------
let seed = 20261106;
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
const pick = (a) => a[Math.floor(rnd() * a.length)];
const LISTS = ['default', 'mayorista', 'minorista', 'vip'];
const products = Array.from({ length: 12 }, (_, i) => ({
  barcode: `P${i}`, name: `Producto ${i}`, stock: pick([0, 1, 2, 3, 5, 10, 100]), tax_rate: pick([0, 5, 19, 8.5]),
  prices: LISTS.filter(() => rnd() < 0.6).map((l) => ({ price_list_name: l, price: Math.round(rnd() * 50000) / (rnd() < 0.3 ? 7 : 1) })),
}));
const clients = [null, ...LISTS.map((l) => ({ document_number: l, document_type: 'CC', price_list: l })), { document_number: 'x', document_type: 'CC', price_list: 'no-existe' }];

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let ok = 0; let fail = 0; const counts = {};
const check = (op, a, b, ctx) => {
  counts[op] = (counts[op] || 0) + 1;
  if (eq(a, b)) ok++; else { fail++; if (fail <= 5) console.log(`FAIL ${op}: ${ctx}\n  nuevo ${JSON.stringify(a)}\n  antes ${JSON.stringify(b)}`); }
};

for (let run = 0; run < 400; run++) {
  let cart = []; let client = pick(clients);
  for (let step = 0; step < 25; step++) {
    const op = pick(['add', 'add', 'add', 'inc', 'dec', 'set', 'remove', 'client']);
    const p = pick(products);
    if (op === 'add') {
      const a = C.addProduct(cart, p, client); const b = orig.addToCart(cart, p, client);
      check('agregar', a, b, `${p.barcode} cliente ${client && client.price_list}`); cart = b.cart;
    } else if (op === 'inc' || op === 'dec') {
      if (!cart.length) continue;
      const line = pick(cart); const delta = op === 'inc' ? 1 : -1;
      const prod = products.find((x) => x.barcode === line.barcode);
      const a = C.changeQuantity(cart, line.barcode, delta, prod); const b = orig.updateQuantity(cart, line.barcode, delta, products);
      check('cambiar cantidad', a, b, `${line.barcode} ${delta}`); cart = b.cart;
    } else if (op === 'set') {
      if (!cart.length) continue;
      const line = pick(cart); const value = pick(['', '0', '-2', '1', '3', '7', '150', 'abc', '2.9', ' 4']);
      const prod = products.find((x) => x.barcode === line.barcode);
      const a = C.setLineQuantity(cart, line.barcode, value, prod); const b = orig.setQuantity(cart, line.barcode, value, products);
      check('escribir cantidad', a, b, `${line.barcode} «${value}»`); cart = b.cart;
    } else if (op === 'remove') {
      if (!cart.length) continue;
      const bc = pick(cart).barcode;
      check('quitar', C.removeLine(cart, bc), cart.filter((i) => i.barcode !== bc), bc); cart = cart.filter((i) => i.barcode !== bc);
    } else {
      const next = pick(clients.filter(Boolean));
      check('cambiar de cliente', C.repriceForClient(cart, products, next), orig.reprice(cart, products, next), next.price_list);
      cart = orig.reprice(cart, products, next); client = next;
    }
    check('totales', C.cartTotals(cart), orig.totals(cart), `${cart.length} líneas`);
  }
}
console.log(Object.entries(counts).map(([k, v]) => `  ${k}: ${v} casos`).join('\n'));
console.log(`\n${fail ? 0 : 1}/1 pruebas OK  (${ok} comparaciones idénticas, ${fail} distintas)`);
process.exit(fail ? 1 : 0);
