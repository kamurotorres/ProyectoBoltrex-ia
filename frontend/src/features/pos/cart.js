// Reglas del carrito del POS como funciones puras (mantenimiento fase 5).
// Antes vivían dentro de pages/POS.js; aquí se pueden probar sin navegador (tests/frontend_cart_check.js
// las compara con el código original). Cada operación devuelve { cart, error }: si hay `error`, el carrito
// no cambia y la pantalla muestra el mensaje (mismos textos que antes).

/** Importes de una línea: subtotal sin IVA, IVA y total. */
export const lineAmounts = (unitPrice, quantity, taxRate) => {
  const subtotal = unitPrice * quantity;
  const taxAmount = (subtotal * taxRate) / 100;
  return { subtotal, tax_amount: taxAmount, total: subtotal + taxAmount };
};

/** P1.17: precio de la lista del cliente; si el producto no la tiene, el de 'default'; si no, null. */
export const priceFor = (product, priceListName) => {
  const prices = product.prices || [];
  const pick = (name) => prices.find((p) => p.price_list_name === name);
  const found = (priceListName && pick(priceListName)) || pick('default');
  return found ? found.price : null;
};

/** Agrega 1 unidad del producto (o suma 1 si ya está). */
export const addProduct = (cart, product, client) => {
  if (!client) return { cart, error: 'Primero selecciona un cliente' };
  const unitPrice = priceFor(product, client.price_list);
  if (unitPrice === null) return { cart, error: `El producto '${product.name}' no tiene precio de venta. Agrégale un precio en Productos.` };
  if (product.stock <= 0) return { cart, error: 'Producto sin stock' };
  const index = cart.findIndex((item) => item.barcode === product.barcode);
  if (index !== -1) {
    const existing = cart[index];
    const quantity = existing.quantity + 1;
    if (quantity > product.stock) return { cart, error: 'Stock insuficiente' };
    return {
      cart: cart.map((item, i) => (i === index ? { ...item, quantity, ...lineAmounts(existing.unit_price, quantity, existing.tax_rate) } : item)),
      error: null,
    };
  }
  return {
    cart: [...cart, {
      barcode: product.barcode,
      product_name: product.name,
      quantity: 1,
      unit_price: unitPrice,
      tax_rate: product.tax_rate,
      ...lineAmounts(unitPrice, 1, product.tax_rate),
    }],
    error: null,
  };
};

/** Botones − / +: cambia la cantidad en `delta` (no baja de 1, no supera el stock). */
export const changeQuantity = (cart, barcode, delta, product) => {
  let error = null;
  const next = cart.map((item) => {
    if (item.barcode !== barcode) return item;
    const quantity = item.quantity + delta;
    if (quantity <= 0) return item;
    if (quantity > product.stock) { error = 'Stock insuficiente'; return item; }
    return { ...item, quantity, ...lineAmounts(item.unit_price, quantity, item.tax_rate) };
  });
  return { cart: error ? cart : next, error };
};

/** Cantidad escrita a mano. Vacío / 0 / negativo: no cambia nada. */
export const setLineQuantity = (cart, barcode, value, product) => {
  const quantity = parseInt(value) || 0;   // eslint-disable-line radix -- igual que el original
  if (quantity <= 0) return { cart, error: null };
  if (product && quantity > product.stock) return { cart, error: 'Stock insuficiente' };
  return { cart: cart.map((item) => (item.barcode === barcode ? { ...item, quantity, ...lineAmounts(item.unit_price, quantity, item.tax_rate) } : item)), error: null };
};

export const removeLine = (cart, barcode) => cart.filter((item) => item.barcode !== barcode);

/** P1.17: al cambiar de cliente, cada línea toma el precio de la lista del nuevo cliente (o 'default'). */
export const repriceForClient = (cart, products, client) => cart.map((item) => {
  const product = products.find((p) => p.barcode === item.barcode);
  if (!product) return item;
  const prices = product.prices || [];
  const found = prices.find((p) => p.price_list_name === client.price_list) || prices.find((p) => p.price_list_name === 'default');
  const unitPrice = found ? found.price : item.unit_price;
  return { ...item, unit_price: unitPrice, ...lineAmounts(unitPrice, item.quantity, item.tax_rate) };
});

export const cartTotals = (cart) => ({
  subtotal: cart.reduce((sum, item) => sum + item.subtotal, 0),
  totalTax: cart.reduce((sum, item) => sum + item.tax_amount, 0),
  total: cart.reduce((sum, item) => sum + item.total, 0),
});
