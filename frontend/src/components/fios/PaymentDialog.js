import React from 'react';
import { CheckCircle2, DollarSign, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { currency as formatCurrency } from '@/lib/format';

// Diálogo «Registrar Abono» de Fios (mantenimiento fase 4). Antes estaba copiado 2 veces en pages/Fios.js
// (listado y detalle del cliente); `suffix` conserva los id / data-testid de cada copia ('' o '-detail').
const PaymentDialog = ({ open, onOpenChange, invoice, form, setForm, paymentMethods, isSubmitting, onSubmit, suffix = '' }) => (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={`payment-dialog${suffix}`}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Registrar Abono
          </DialogTitle>
        </DialogHeader>
        {invoice && (
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="p-4 bg-muted/30 rounded-lg space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Factura:</span>
                <span className="font-mono">{invoice.invoice_number}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total Factura:</span>
                <span className="font-mono">{formatCurrency(invoice.total)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Ya Abonado:</span>
                <span className="font-mono text-green-400">{formatCurrency(invoice.amount_paid)}</span>
              </div>
              <div className="flex justify-between font-bold border-t border-border pt-2">
                <span>Saldo Pendiente:</span>
                <span className="font-mono text-red-400">{formatCurrency(invoice.balance)}</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor={`amount${suffix}`}>Monto a Abonar *</Label>
              <Input
                id={`amount${suffix}`}
                type="number"
                step="0.01"
                min="0.01"
                max={invoice.balance}
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                placeholder="0.00"
                data-testid={`input-payment-amount${suffix}`}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor={`payment_method${suffix}`}>Forma de Pago *</Label>
              <Select
                value={form.payment_method}
                onValueChange={(value) => setForm({ ...form, payment_method: value })}
              >
                <SelectTrigger data-testid={`select-payment-method${suffix}`}>
                  <SelectValue placeholder="Seleccione..." />
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

            <div className="space-y-2">
              <Label htmlFor={`notes${suffix}`}>Notas (opcional)</Label>
              <Textarea
                id={`notes${suffix}`}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Observaciones del pago..."
                rows={2}
                data-testid={`input-payment-notes${suffix}`}
              />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting} data-testid={`submit-payment-btn${suffix}`}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Registrando...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Registrar Abono
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
);

export default PaymentDialog;
