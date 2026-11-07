import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, CalendarClock, CreditCard, Loader2, Minus, Plus, ShoppingCart, Trash2, Wallet } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { ymd } from '@/features/pos/usePosState';
import { money as money0, ymdToDmy as dmy } from '@/lib/format';

// Extraído de POS.js (mantenimiento fase 5) sin cambios en el JSX.
export default function CartSection({ canCreate, cart, cashState, creditStatus, dueDate, handleCheckout, isProcessing, paymentMethods, paymentStatus, removeFromCart, selectedClient, selectedPaymentMethod, setCart, setDueDate, setPaymentStatus, setQuantity, setSelectedPaymentMethod, totals, updateQuantity }) {
  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <ShoppingCart className="h-5 w-5" />
          3. Carrito de Compra
          {cart.length > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-primary text-primary-foreground rounded-full text-sm">
              {cart.length} items
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {cart.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <ShoppingCart className="h-16 w-16 mx-auto mb-4 opacity-30" />
            <p className="text-lg">El carrito está vacío</p>
            <p className="text-sm">Busca y agrega productos para comenzar</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Cart Items Table */}
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium">Producto</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">Precio Unit.</th>
                    <th className="px-4 py-3 text-center text-sm font-medium">Cantidad</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">Subtotal</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">IVA</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">Total</th>
                    <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {cart.map((item, index) => (
                    <tr key={item.barcode} data-testid={`cart-item-${index}`}>
                      <td className="px-4 py-3">
                        <p className="font-medium">{item.product_name}</p>
                        <p className="text-xs text-muted-foreground font-mono">{item.barcode}</p>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {money0(item.unit_price)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => updateQuantity(item.barcode, -1)}
                          >
                            <Minus className="h-4 w-4" />
                          </Button>
                          <input
                            type="number"
                            min="1"
                            className="w-16 text-center font-mono font-bold bg-transparent border rounded-md h-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                            value={item.quantity}
                            onFocus={(e) => e.target.select()}
                            onChange={(e) => {
                              const val = e.target.value;
                              if (val === '') {
                                setCart(cart.map(ci => ci.barcode === item.barcode ? { ...ci, quantity: '' } : ci));
                              } else {
                                setQuantity(item.barcode, val);
                              }
                            }}
                            onBlur={(e) => {
                              if (!e.target.value || parseInt(e.target.value) <= 0) {
                                setQuantity(item.barcode, 1);
                              }
                            }}
                            data-testid={`cart-quantity-input-${item.barcode}`}
                          />
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => updateQuantity(item.barcode, 1)}
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {money0(item.subtotal)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm text-muted-foreground">
                        {money0(item.tax_amount)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-bold">
                        {money0(item.total)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => removeFromCart(item.barcode)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totals and Payment */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Payment Options */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Wallet className="h-4 w-4" />
                    Estado de Pago
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant={paymentStatus === 'pagado' ? 'default' : 'outline'}
                      className={`w-full h-12 ${paymentStatus === 'pagado' ? 'bg-green-600 hover:bg-green-700' : ''}`}
                      onClick={() => setPaymentStatus('pagado')}
                      data-testid="payment-status-pagado"
                    >
                      <CreditCard className="h-4 w-4 mr-2" />
                      Pagado
                    </Button>
                    <Button
                      type="button"
                      variant={paymentStatus === 'por_cobrar' ? 'default' : 'outline'}
                      className={`w-full h-12 ${paymentStatus === 'por_cobrar' ? 'bg-orange-600 hover:bg-orange-700' : ''}`}
                      onClick={() => setPaymentStatus('por_cobrar')}
                      data-testid="payment-status-por-cobrar"
                    >
                      <Wallet className="h-4 w-4 mr-2" />
                      Por Cobrar
                    </Button>
                  </div>
                </div>

                {paymentStatus === 'pagado' && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4" />
                      Forma de Pago *
                    </Label>
                    <Select
                      value={selectedPaymentMethod}
                      onValueChange={setSelectedPaymentMethod}
                    >
                      <SelectTrigger className="h-12" data-testid="select-payment-method">
                        <SelectValue placeholder="Seleccione forma de pago" />
                      </SelectTrigger>
                      <SelectContent>
                        {paymentMethods.map((pm) => (
                          <SelectItem key={pm.name} value={pm.name}>
                            {pm.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {paymentStatus === 'por_cobrar' && (
                  <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg space-y-3">
                    <p className="text-sm text-orange-400">
                      <Wallet className="h-4 w-4 inline mr-2" />
                      La factura se registrará como crédito y aparecerá en el módulo de Fios.
                    </p>
                    <div className="space-y-1">
                      <Label htmlFor="pos-due-date" className="flex items-center gap-2 text-sm">
                        <CalendarClock className="h-4 w-4" /> Fecha de vencimiento
                      </Label>
                      <Input id="pos-due-date" type="date" min={ymd(new Date())} value={dueDate}
                             onChange={(e) => setDueDate(e.target.value)} className="max-w-[12rem]" data-testid="pos-due-date-input" />
                      <p className="text-xs text-muted-foreground">
                        {creditStatus
                          ? `Plazo ${creditStatus.term_days === creditStatus.default_term_days ? 'por defecto' : 'del cliente'}: ${creditStatus.term_days} día(s)`
                            + (dueDate ? ` · vence el ${dmy(dueDate)}` : '')
                          : 'Vacío: se usa el plazo del cliente o el de Config. Sistema.'}
                      </p>
                    </div>
                    {creditStatus && creditStatus.credit_limit && totals.total > (creditStatus.available || 0) + 0.005 && (
                      <p className="text-sm text-red-400" data-testid="pos-credit-limit-warning">
                        <AlertTriangle className="h-4 w-4 inline mr-2" />
                        Esta venta ({money0(totals.total)}) supera el cupo disponible del cliente ({money0(Math.max(0, creditStatus.available))}).
                        No se puede fiar: cóbrala de contado o pide a un administrador que amplíe el cupo.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Totals Summary */}
              <div className="bg-muted/30 rounded-lg p-6 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Subtotal:</span>
                  <span className="font-mono" data-testid="cart-subtotal">
                    {money0(totals.subtotal)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">IVA Total:</span>
                  <span className="font-mono" data-testid="cart-tax">
                    {money0(totals.totalTax)}
                  </span>
                </div>
                <div className="border-t pt-3">
                  <div className="flex justify-between text-2xl font-bold">
                    <span>TOTAL:</span>
                    <span className="font-mono text-primary" data-testid="cart-total">
                      {money0(totals.total)}
                    </span>
                  </div>
                </div>

                <Button
                  className="w-full h-14 text-lg mt-4 font-semibold shadow-md"
                  size="lg"
                  onClick={handleCheckout}
                  disabled={isProcessing || cart.length === 0 || !selectedClient || (paymentStatus === 'pagado' && !selectedPaymentMethod) || !canCreate('pos') || (cashState.required && !cashState.open)
                    || (paymentStatus === 'por_cobrar' && creditStatus && creditStatus.credit_limit && totals.total > (creditStatus.available || 0) + 0.005)}
                  data-testid="checkout-button"
                  title={!canCreate('pos') ? 'Tu rol no tiene permiso para registrar ventas' : undefined}
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Procesando venta...
                    </>
                  ) : paymentStatus === 'pagado' ? (
                    <>
                      <CreditCard className="h-5 w-5 mr-2" />
                      Procesar Venta (Pagado)
                    </>
                  ) : (
                    <>
                      <Wallet className="h-5 w-5 mr-2" />
                      Procesar Venta (Crédito)
                    </>
                  )}
                </Button>
                {!canCreate('pos') && (
                  <p className="text-xs text-center text-muted-foreground mt-2" data-testid="pos-no-permission">
                    Tu rol no tiene permiso para registrar ventas. Pídeselo a un administrador.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
