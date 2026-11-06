import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { getErrorMessage } from '@/lib/utils';
import { money } from '@/lib/format';
import { api } from '@/api/client';

// Movido de Cash.js sin cambios (mantenimiento fase 5).
export function CloseDialog({ open, onOpenChange, cashSession, denoms, forced, onClosed }) {
  const [mode, setMode] = useState('denominations');
  const [qty, setQty] = useState({});
  const [total, setTotal] = useState('');
  const [notes, setNotes] = useState('');
  const [reconciled, setReconciled] = useState({});
  const [saving, setSaving] = useState(false);
  const expected = cashSession?.summary?.expected_cash || 0;
  const all = [...denoms.bills, ...denoms.coins];
  const counted = mode === 'denominations'
    ? all.reduce((sum, d) => sum + d * (parseInt(qty[d], 10) || 0), 0)
    : parseFloat(total) || 0;
  const diff = Math.round((counted - expected) * 100) / 100;
  const others = (cashSession?.summary?.methods || []).filter((m) => !m.is_cash && m.expected);

  useEffect(() => {
    if (open) { setQty({}); setTotal(''); setNotes(''); setReconciled({}); setMode('denominations'); }
  }, [open]);

  const submit = async () => {
    if (diff !== 0 && !notes.trim()) {
      toast.error(`Hay ${diff > 0 ? 'un sobrante' : 'un faltante'} de ${money(Math.abs(diff))}: escribe una observación para cerrar.`);
      return;
    }
    if (forced && !notes.trim()) {
      toast.error('Para cerrar la caja de otro cajero escribe el motivo en observaciones.');
      return;
    }
    setSaving(true);
    try {
      const body = { notes, reconciled };
      if (mode === 'denominations') {
        body.denominations = Object.fromEntries(all.filter((d) => parseInt(qty[d], 10) > 0).map((d) => [String(d), parseInt(qty[d], 10)]));
        if (!Object.keys(body.denominations).length) body.counted_cash = 0;
      } else {
        body.counted_cash = counted;
      }
      const res = await api.post(`/cash/sessions/${cashSession.session_id}/close`, body);
      toast.success(`Caja ${cashSession.session_id} cerrada${res.data.difference ? ` con ${res.data.difference > 0 ? 'sobrante' : 'faltante'} de ${money(Math.abs(res.data.difference))}` : ' cuadrada'}.`);
      onClosed(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cerrar la caja'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="close-cash-dialog">
        <DialogHeader>
          <DialogTitle>Cerrar caja {cashSession?.session_id}{forced ? ` de ${cashSession?.cashier_email}` : ''}</DialogTitle>
          <DialogDescription>Cuenta el efectivo y compáralo con lo que debería haber.</DialogDescription>
        </DialogHeader>
        <div className="flex gap-1">
          <Button size="sm" variant={mode === 'denominations' ? 'default' : 'outline'} onClick={() => setMode('denominations')}>Por billetes y monedas</Button>
          <Button size="sm" variant={mode === 'total' ? 'default' : 'outline'} onClick={() => setMode('total')}>Solo el total</Button>
        </div>
        {mode === 'denominations' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {all.map((d) => (
              <label key={d} className="flex items-center gap-2 text-sm">
                <span className="w-20 text-right font-mono">{money(d)}</span>
                <span className="text-muted-foreground">×</span>
                <Input type="number" min="0" step="1" className="h-8" value={qty[d] ?? ''} onChange={(e) => setQty((q) => ({ ...q, [d]: e.target.value }))}
                       aria-label={`Cantidad de ${money(d)}`} data-testid={`denom-${d}`} />
              </label>
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            <Label>Efectivo contado</Label>
            <Input type="number" min="0" value={total} onChange={(e) => setTotal(e.target.value)} data-testid="counted-total" />
          </div>
        )}
        <div className="grid grid-cols-3 gap-2 rounded-md border border-border p-3 text-sm">
          <div><p className="text-xs text-muted-foreground">Esperado</p><p className="font-mono font-semibold">{money(expected)}</p></div>
          <div><p className="text-xs text-muted-foreground">Contado</p><p className="font-mono font-semibold">{money(counted)}</p></div>
          <div>
            <p className="text-xs text-muted-foreground">Diferencia</p>
            <p className={`font-mono font-semibold ${diff === 0 ? '' : diff > 0 ? 'text-green-500' : 'text-red-500'}`} data-testid="close-diff">
              {diff === 0 ? 'Cuadrada ✓' : `${diff > 0 ? 'Sobrante +' : 'Faltante −'}${money(Math.abs(diff))}`}
            </p>
          </div>
        </div>
        {others.length > 0 && (
          <div className="space-y-1">
            <p className="text-sm font-medium">Otras formas de pago (verifica con los comprobantes)</p>
            {others.map((m) => (
              <label key={m.method} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!reconciled[m.method]} onChange={(e) => setReconciled((r) => ({ ...r, [m.method]: e.target.checked }))} />
                {m.method}: <span className="font-mono">{money(m.expected)}</span> conciliado
              </label>
            ))}
          </div>
        )}
        <div className="space-y-1">
          <Label>Observaciones {diff !== 0 || forced ? '*' : '(opcional)'}</Label>
          <Input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500}
                 placeholder={forced ? 'Motivo del cierre forzado' : diff !== 0 ? 'Explica la diferencia' : ''} data-testid="close-notes" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={submit} disabled={saving} data-testid="confirm-close-cash"><Lock className="h-4 w-4 mr-2" />{saving ? 'Cerrando…' : 'Cerrar caja'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default CloseDialog;
