// P1.16/P1.17: mismas reglas que el backend (core/pricing.py). El backend vuelve a validar.
// Fase 6: pricingIssues devuelve TODOS los problemas con el campo de cada uno (para mostrarlos debajo de
// cada campo); pricingProblem devuelve el primero, igual que antes (tests/frontend_forms_check.js compara
// con la versión original).
export const DEFAULT_PRICE_LIST = 'default';

/** [{ path, message }] en el mismo orden en que la versión original los revisaba.
 *  Los errores de la sección completa van en prices.root (así no pisan los de cada fila). */
export const pricingIssues = ({ purchase_price, tax_rate, prices }) => {
  const issues = [];
  const add = (path, message) => issues.push({ path, message });
  const cost = parseFloat(purchase_price);
  const costOk = !Number.isNaN(cost) && cost >= 0;
  if (Number.isNaN(cost)) add(['purchase_price'], 'El precio de compra debe ser un número.');
  else if (cost < 0) add(['purchase_price'], 'El precio de compra no puede ser negativo.');
  const iva = parseFloat(tax_rate);
  if (Number.isNaN(iva) || iva < 0 || iva > 100) add(['tax_rate'], 'El IVA debe estar entre 0 y 100 %.');
  const all = prices || [];
  const rows = all.map((p, index) => ({ p, index })).filter(({ p }) => p.price_list_name || p.price !== '');
  if (rows.length === 0) {
    add(['prices', 'root'], "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'.");
    return issues;
  }
  const seen = new Set();
  for (const { p, index } of rows) {
    if (!p.price_list_name) { add(['prices', index, 'price_list_name'], 'Cada precio de venta debe tener su lista de precios.'); continue; }
    if (seen.has(p.price_list_name)) { add(['prices', index, 'price_list_name'], `La lista de precios '${p.price_list_name}' está repetida.`); continue; }
    seen.add(p.price_list_name);
    const price = parseFloat(p.price);
    if (Number.isNaN(price) || price <= 0) add(['prices', index, 'price'], `El precio de la lista '${p.price_list_name}' debe ser mayor a 0.`);
    else if (costOk && price < cost) add(['prices', index, 'price'], `El precio de venta de la lista '${p.price_list_name}' no puede ser menor que el precio de compra.`);
  }
  if (!seen.has(DEFAULT_PRICE_LIST)) {
    add(['prices', 'root'], "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio.");
  }
  return issues;
};

export const pricingProblem = (data) => {
  const [first] = pricingIssues(data);
  return first ? first.message : null;
};

export default pricingProblem;
