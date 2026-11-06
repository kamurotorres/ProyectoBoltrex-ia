import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

// Extraído de Cash.js (mantenimiento fase 5) sin cambios en el JSX.
export default function MovementDialog({ busy, mov, movOpen, saveMovement, setMov, setMovOpen }) {
  return (
    <Dialog open={movOpen} onOpenChange={setMovOpen}>
      <DialogContent data-testid="cash-movement-dialog">
        <DialogHeader>
          <DialogTitle>Registrar movimiento de efectivo</DialogTitle>
          <DialogDescription>Ingreso (p. ej. más sencillo) o egreso (gasto, pago, retiro a la caja fuerte).</DialogDescription>
        </DialogHeader>
        <div className="flex gap-1">
          <Button size="sm" variant={mov.kind === 'income' ? 'default' : 'outline'} onClick={() => setMov((m) => ({ ...m, kind: 'income' }))}>Ingreso</Button>
          <Button size="sm" variant={mov.kind === 'expense' ? 'default' : 'outline'} onClick={() => setMov((m) => ({ ...m, kind: 'expense' }))}>Egreso</Button>
        </div>
        <div className="space-y-1"><Label>Monto *</Label><Input type="number" min="0" value={mov.amount} onChange={(e) => setMov((m) => ({ ...m, amount: e.target.value }))} /></div>
        <div className="space-y-1"><Label>Motivo *</Label><Input value={mov.reason} maxLength={200} onChange={(e) => setMov((m) => ({ ...m, reason: e.target.value }))} /></div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setMovOpen(false)}>Cancelar</Button>
          <Button onClick={saveMovement} disabled={busy}>Guardar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
