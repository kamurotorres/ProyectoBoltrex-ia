import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Package, Plus, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

// Extraído de POS.js (mantenimiento fase 5) sin cambios en el JSX.
export default function ProductSection({ addToCart, cart, filteredProducts, getProductPrice, searchProduct, searchingProducts, selectedClient, setSearchProduct }) {
  return (
    <Card className={`w-full ${!selectedClient ? 'opacity-50 pointer-events-none' : ''}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Package className="h-5 w-5" />
          2. Agregar Productos
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar producto por nombre o código de barras... (mínimo 2 caracteres)"
            value={searchProduct}
            onChange={(e) => setSearchProduct(e.target.value)}
            className="pl-10 text-lg h-12"
            disabled={!selectedClient}
            data-testid="pos-search-product-input"
          />
        </div>

        {/* Show products only when searching */}
        {searchProduct.length >= 2 && (
          <div className="border rounded-lg overflow-hidden">
            {filteredProducts.length > 0 ? (
              <div className="divide-y">
                {filteredProducts.map((product, index) => {
                  const price = getProductPrice(product);
                  const inCart = cart.find(item => item.barcode === product.barcode);

                  return (
                    <div
                      key={product.barcode}
                      className={`flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all ${
                        inCart ? 'bg-green-500/5' : ''
                      }`}
                      onClick={() => addToCart(product)}
                      data-testid={`pos-product-${index}`}
                    >
                      <div className="flex-1">
                        <p className="font-semibold">{product.name}</p>
                        <p className="text-sm text-muted-foreground font-mono">{product.barcode}</p>
                      </div>
                      <div className="text-right mr-4">
                        {price === null ? (
                          <p className="text-sm font-semibold text-red-500">Sin precio de venta</p>
                        ) : (
                          <p className="font-bold text-lg font-mono text-primary">
                            ${price.toLocaleString()}
                          </p>
                        )}
                        <p className={`text-xs ${product.stock > 0 ? 'text-muted-foreground' : 'text-red-500'}`}>
                          Stock: {product.stock}
                        </p>
                      </div>
                      {inCart && (
                        <div className="px-3 py-1 bg-green-500/20 text-green-500 rounded-full text-sm font-medium">
                          En carrito: {inCart.quantity}
                        </div>
                      )}
                      <Button size="sm" className="ml-4">
                        <Plus className="h-4 w-4 mr-1" />
                        Agregar
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 text-center text-muted-foreground">
                <Package className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>{searchingProducts ? 'Buscando…' : `No se encontraron productos para "${searchProduct}"`}</p>
              </div>
            )}
          </div>
        )}

        {searchProduct.length > 0 && searchProduct.length < 2 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Escribe al menos 2 caracteres para buscar productos
          </p>
        )}
      </CardContent>
    </Card>
  );
}
