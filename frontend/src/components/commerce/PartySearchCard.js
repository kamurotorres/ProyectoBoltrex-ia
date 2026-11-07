import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// Paso «elegir a quién» del POS (cliente) y de Compras (proveedor) — rama compras-estilo-pos.
// Diseño sacado TAL CUAL del POS (features/pos/ClientSection): naranja mientras falta, verde cuando está elegido.
//   results: lo que encontró la búsqueda · renderResult(item) → { title, subtitle, side } de cada fila.
export default function PartySearchCard({
  step, title, icon: Icon, selected, selectedTitle, selectedLines, onClear, changeLabel, hint, placeholder,
  query, onQueryChange, results, searching, renderResult, onSelect, noun, inputTestId, rowTestId, resultKey, children,
}) {
  return (
    <Card className={`w-full ${!selected ? 'border-orange-500/50 bg-orange-500/5' : 'border-green-500/50 bg-green-500/5'}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Icon className="h-5 w-5" />
          {step}. {title}
          <span className="text-xs text-orange-500 font-normal">(Requerido)</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {selected ? (
          <div className="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <Icon className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="font-semibold text-lg">{selectedTitle}</p>
                {selectedLines}
              </div>
            </div>
            {onClear && (
              <Button
                variant="outline"
                onClick={onClear}
              >
                {changeLabel}
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/30 rounded-md">
              <AlertCircle className="h-5 w-5 text-orange-400" />
              <p className="text-sm text-orange-400">{hint}</p>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder={placeholder}
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                className="pl-10 text-lg h-12"
                data-testid={inputTestId}
              />
            </div>

            {/* Show results only when searching */}
            {query.length >= 2 && (
              <div className="border rounded-lg overflow-hidden">
                {results.length > 0 ? (
                  <div className="divide-y">
                    {results.map((item, index) => {
                      const row = renderResult(item);
                      return (
                        <div
                          key={resultKey(item)}
                          className="flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all"
                          onClick={() => onSelect(item)}
                          data-testid={`${rowTestId}-${index}`}
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                              <Icon className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <p className="font-medium">{row.title}</p>
                              <p className="text-sm text-muted-foreground font-mono">{row.subtitle}</p>
                            </div>
                          </div>
                          <div className="text-right mr-4">
                            {row.side}
                          </div>
                          <Button size="sm">
                            Seleccionar
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-8 text-center text-muted-foreground">
                    <Icon className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>{searching ? 'Buscando…' : `No se encontraron ${noun} para "${query}"`}</p>
                  </div>
                )}
              </div>
            )}

            {query.length > 0 && query.length < 2 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                Escribe al menos 2 caracteres para buscar {noun}
              </p>
            )}
          </div>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
