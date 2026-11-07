import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowDown, ArrowUp, CheckCircle, Info, Loader2, Save, ShoppingBag, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FieldError } from '@/components/form/Field';
import QuantityStepper from '@/components/commerce/QuantityStepper';
import { money, number } from '@/lib/format';

// Paso 3 de la compra: detalle + total + acciones (rama compras-estilo-pos). Mismo estilo que el carrito del POS,
// con lo que importa al comprar: costo actual vs. nuevo y stock actual → después.
export default function PurchaseItemsSection({ purchaseForm, step, readonly, canSave, canProcess, saving, onSaveDraft, onSaveAndProcess }) {
  const { items, known, errors, removeItem, stepItemQuantity, typeItemQuantity, setItemQuantity, updateItemField, calculateTotal, totalUnits } = purchaseForm;
  const itemsError = errors.items?.message ? errors.items : errors.items?.root;
  const rowError = (index) => errors.items?.[index]?.quantity || errors.items?.[index]?.unit_cost;

  const costHint = (item) => {
    const before = known[item.barcode]?.purchase_price;
    const now = parseFloat(item.unit_cost);
    if (readonly || before == null || Number.isNaN(now) || Math.abs(now - before) < 0.005) return null;
    if (now === 0) return <span className="text-xs text-muted-foreground">regalo: no cambia el costo</span>;
    const up = now > before;
    return (
      <span className={`text-xs inline-flex items-center gap-0.5 ${up ? 'text-red-400' : 'text-green-400'}`} data-testid={`cost-change-${item.barcode}`}>
        {up ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}antes {money(before)}
      </span>
    );
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <ShoppingBag className="h-5 w-5" />
          {step}. Detalle de la Compra
          {items.length > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-primary text-primary-foreground rounded-full text-sm">
              {items.length} productos
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <ShoppingBag className="h-16 w-16 mx-auto mb-4 opacity-30" />
            <p className="text-lg">La compra no tiene productos</p>
            <p className="text-sm">Busca o escanea productos para agregarlos</p>
            <FieldError error={itemsError} id="purchase-items-error" />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium">Producto</th>
                    <th className="px-4 py-3 text-center text-sm font-medium">Cantidad</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">Costo Unit.</th>
                    {!readonly && <th className="px-4 py-3 text-center text-sm font-medium">Stock</th>}
                    <th className="px-4 py-3 text-right text-sm font-medium">Total</th>
                    {!readonly && <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {items.map((item, index) => {
                    const stock = known[item.barcode]?.stock;
                    return (
                      <tr key={item.barcode} data-testid={`purchase-item-${index}`}>
                        <td className="px-4 py-3">
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs text-muted-foreground font-mono">{item.barcode}</p>
                          <FieldError error={rowError(index)} id={`item-error-${item.barcode}`} />
                        </td>
                        <td className="px-4 py-3">
                          {readonly ? (
                            <div className="text-center font-mono font-bold">{item.quantity}</div>
                          ) : (
                            <QuantityStepper value={item.quantity} onStep={(d) => stepItemQuantity(item.barcode, d)}
                                             onType={(v) => typeItemQuantity(item.barcode, v)} onBlurEmpty={() => setItemQuantity(item.barcode, 1)}
                                             testId={`item-quantity-${item.barcode}`} />
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {readonly ? (
                            <span className="font-mono">{money(item.unit_cost)}</span>
                          ) : (
                            <div className="flex flex-col items-end gap-0.5">
                              <div className="flex items-center gap-1">
                                <span className="text-muted-foreground">$</span>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  className="w-28 text-right font-mono bg-transparent border rounded-md h-8 px-2 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                  value={item.unit_cost}
                                  onFocus={(e) => e.target.select()}
                                  onChange={(e) => updateItemField(item.barcode, 'unit_cost', e.target.value)}
                                  onBlur={(e) => { if (!e.target.value) updateItemField(item.barcode, 'unit_cost', 0); }}
                                  data-testid={`item-cost-${item.barcode}`}
                                />
                              </div>
                              {costHint(item)}
                            </div>
                          )}
                        </td>
                        {!readonly && (
                          <td className="px-4 py-3 text-center font-mono text-sm" data-testid={`item-stock-${item.barcode}`}>
                            {stock == null ? '—' : <>{number(stock)} → <span className="font-bold">{number(stock + (parseInt(item.quantity) || 0))}</span></>}
                          </td>
                        )}
                        <td className="px-4 py-3 text-right font-mono font-bold">{money(item.total)}</td>
                        {!readonly && (
                          <td className="px-4 py-3 text-center">
                            <Button variant="ghost" size="icon" type="button" className="text-destructive hover:text-destructive"
                                    onClick={() => removeItem(item.barcode)} title="Quitar">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="text-sm text-muted-foreground space-y-2">
                {!readonly && (
                  <p className="flex items-start gap-2">
                    <Info className="h-4 w-4 mt-0.5 shrink-0" />
                    <span>
                      Al <strong>procesar</strong>, las unidades entran al inventario y el costo de cada producto pasa a ser el de
                      esta compra (las líneas en $0, como regalos del proveedor, no lo cambian). El borrador se puede editar después.
                    </span>
                  </p>
                )}
              </div>
              <div className="space-y-3">
                <div className="p-4 bg-muted/30 rounded-lg space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Productos / unidades</span>
                    <span className="font-mono" data-testid="purchase-units">{items.length} / {number(totalUnits())}</span>
                  </div>
                  <div className="flex justify-between text-xl font-bold pt-2 border-t">
                    <span>TOTAL</span>
                    <span className="font-mono text-primary" data-testid="purchase-total">{money(calculateTotal())}</span>
                  </div>
                </div>
                {!readonly && (
                  <div className="grid grid-cols-2 gap-2">
                    <Button type="button" variant="outline" className="h-12" disabled={!canSave || saving} onClick={onSaveDraft}
                            data-testid="save-purchase-button">
                      {saving === 'draft' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                      Guardar borrador
                    </Button>
                    <Button type="button" className="h-12 bg-green-600 hover:bg-green-700" disabled={!canProcess || saving}
                            onClick={onSaveAndProcess} data-testid="save-and-process-purchase-button"
                            title={canProcess ? undefined : 'Necesitas permiso para editar compras'}>
                      {saving === 'process' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                      Guardar y procesar
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
