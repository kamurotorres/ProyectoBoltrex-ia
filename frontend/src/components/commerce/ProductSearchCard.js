import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Package, Plus, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

// Paso «agregar productos» del POS y de Compras — rama compras-estilo-pos. Diseño sacado TAL CUAL del POS
// (features/pos/ProductSection). Lector de código de barras (decisión 3.A): Enter con el código → onScan(código).
//   renderSide(product) → lo de la derecha (precio y stock en el POS; costo y stock en Compras)
//   inListLabel(product) → «En carrito: 2» / «En la compra: 2» o null
export default function ProductSearchCard({
  step, enabled = true, query, onQueryChange, onScan, results, searching, onAdd, renderSide, inListLabel, inputTestId, rowTestId,
}) {
  const handleKeyDown = (e) => {
    if (e.key !== 'Enter' || !onScan) return;
    e.preventDefault();
    const code = query.trim();
    if (code) onScan(code);
  };
  return (
    <Card className={`w-full ${!enabled ? 'opacity-50 pointer-events-none' : ''}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Package className="h-5 w-5" />
          {step}. Agregar Productos
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar producto por nombre o código de barras... (mínimo 2 caracteres)"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-10 text-lg h-12"
            disabled={!enabled}
            data-testid={inputTestId}
          />
        </div>

        {/* Show products only when searching */}
        {query.length >= 2 && (
          <div className="border rounded-lg overflow-hidden">
            {results.length > 0 ? (
              <div className="divide-y">
                {results.map((product, index) => {
                  const inList = inListLabel(product);

                  return (
                    <div
                      key={product.barcode}
                      className={`flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all ${
                        inList ? 'bg-green-500/5' : ''
                      }`}
                      onClick={() => onAdd(product)}
                      data-testid={`${rowTestId}-${index}`}
                    >
                      <div className="flex-1">
                        <p className="font-semibold">{product.name}</p>
                        <p className="text-sm text-muted-foreground font-mono">{product.barcode}</p>
                      </div>
                      <div className="text-right mr-4">
                        {renderSide(product)}
                      </div>
                      {inList && (
                        <div className="px-3 py-1 bg-green-500/20 text-green-500 rounded-full text-sm font-medium">
                          {inList}
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
                <p>{searching ? 'Buscando…' : `No se encontraron productos para "${query}"`}</p>
              </div>
            )}
          </div>
        )}

        {query.length > 0 && query.length < 2 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Escribe al menos 2 caracteres para buscar productos
          </p>
        )}
      </CardContent>
    </Card>
  );
}
