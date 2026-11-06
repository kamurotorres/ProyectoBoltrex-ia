import React, {} from 'react';

// Movido de Products.js sin cambios (mantenimiento fase 5).
// P1.16/P1.17: mismas reglas que el backend (core/pricing.py). El backend vuelve a validar.
export const DEFAULT_PRICE_LIST = 'default';

export const pricingProblem = ({ purchase_price, tax_rate, prices }) => {
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
  if (!seen.has(DEFAULT_PRICE_LIST)) {
    return "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio.";
  }
  return null;
};

export default pricingProblem;
