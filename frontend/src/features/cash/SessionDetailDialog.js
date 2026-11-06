import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { money, shortDateTime as when } from '@/lib/format';
import SummaryTable, { Movements, printReport } from '@/features/cash/SessionParts';
import { Button } from '@/components/ui/button';
import { Lock, Printer } from 'lucide-react';
import ExportMenu from '@/components/ExportMenu';
import { API } from '@/api/client';

// Extraído de Cash.js (mantenimiento fase 5) sin cambios en el JSX.
export default function SessionDetailDialog({ canUpdate, detail, isAdmin, setCloseTarget, setDetail, user }) {
  return (
    <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="cash-detail-dialog">
        {detail && (
          <>
            <DialogHeader>
              <DialogTitle>Caja {detail.session_id} · {detail.status === 'open' ? 'abierta' : 'cerrada'}</DialogTitle>
              <DialogDescription>
                {detail.cashier_name} ({detail.cashier_email}) · apertura {when(detail.opened_at)}
                {detail.closed_at ? ` · cierre ${when(detail.closed_at)}${detail.forced_close ? ` por ${detail.closed_by} (forzado)` : ''}` : ''}
              </DialogDescription>
            </DialogHeader>
            {detail.status === 'closed' && (
              <div className="grid grid-cols-3 gap-2 rounded-md border border-border p-3 text-sm">
                <div><p className="text-xs text-muted-foreground">Esperado</p><p className="font-mono">{money(detail.summary?.expected_cash)}</p></div>
                <div><p className="text-xs text-muted-foreground">Contado</p><p className="font-mono">{money(detail.counted_cash)}</p></div>
                <div><p className="text-xs text-muted-foreground">Diferencia</p><p className="font-mono">{detail.difference ? `${detail.difference > 0 ? '+' : '−'}${money(Math.abs(detail.difference))}` : 'Cuadrada'}</p></div>
                {detail.closing_notes && <p className="col-span-3 text-xs text-muted-foreground">Observaciones: {detail.closing_notes}</p>}
              </div>
            )}
            <SummaryTable summary={detail.summary} />
            <Movements movements={detail.movements} />
            <DialogFooter>
              {detail.status === 'closed' && <Button variant="outline" onClick={() => printReport(detail)}><Printer className="h-4 w-4 mr-2" />Imprimir cierre</Button>}
              {/* P2.33: cierre en PDF A4 (movimientos, por forma de pago y arqueo) o Excel */}
              <ExportMenu url={`${API}/cash/sessions/${detail.session_id}/export`} formats={['pdf', 'xlsx']} label="Descargar"
                          fallbackName={`caja_${detail.session_id}`} testId="cash-export-button" />
              {detail.status === 'open' && isAdmin && detail.cashier_email !== user?.email && canUpdate('cash') && (
                <Button onClick={() => { setCloseTarget(detail); setDetail(null); }} data-testid="force-close-button"><Lock className="h-4 w-4 mr-2" />Cerrar (forzado)</Button>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
