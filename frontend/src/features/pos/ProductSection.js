import React from 'react';
import { money } from '@/lib/format';
import ProductSearchCard from '@/components/commerce/ProductSearchCard';

// Paso 2 del POS. Diseño compartido con Compras (components/commerce/ProductSearchCard, rama compras-estilo-pos).
// onScan: lector de código de barras (Enter con el código exacto agrega el producto).
export default function ProductSection({ addToCart, cart, filteredProducts, getProductPrice, onScan, searchProduct, searchingProducts, selectedClient, setSearchProduct }) {
  return (
    <ProductSearchCard
      step={2}
      enabled={!!selectedClient}
      query={searchProduct}
      onQueryChange={setSearchProduct}
      onScan={onScan}
      results={filteredProducts}
      searching={searchingProducts}
      onAdd={addToCart}
      renderSide={(product) => {
        const price = getProductPrice(product);
        return (
          <>
            {price === null ? (
              <p className="text-sm font-semibold text-red-500">Sin precio de venta</p>
            ) : (
              <p className="font-bold text-lg font-mono text-primary">
                {money(price)}
              </p>
            )}
            <p className={`text-xs ${product.stock > 0 ? 'text-muted-foreground' : 'text-red-500'}`}>
              Stock: {product.stock}
            </p>
          </>
        );
      }}
      inListLabel={(product) => {
        const inCart = cart.find(item => item.barcode === product.barcode);
        return inCart ? `En carrito: ${inCart.quantity}` : null;
      }}
      inputTestId="pos-search-product-input"
      rowTestId="pos-product"
    />
  );
}
