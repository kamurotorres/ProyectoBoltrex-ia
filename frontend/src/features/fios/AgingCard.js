import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, CalendarClock } from 'lucide-react';
import { currency as formatCurrency } from '@/lib/format';

// Extraído de Fios.js (mantenimiento fase 5) sin cambios en el JSX.
export default function AgingCard({ aging, setStatusFilter, statusFilter }) {
  return (
    <Card data-testid="fios-aging">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <CalendarClock className="h-4 w-4" /> Antigüedad de la cartera
          {aging.overdue_balance > 0 && (
            <span className="ml-auto text-sm font-normal text-red-400 flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              Vencido {formatCurrency(aging.overdue_balance)} · {aging.overdue_clients} cliente(s)
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {aging.buckets.map((b) => {
            const key = b.key === 'current' ? 'current' : b.key;
            const active = statusFilter === key;
            return (
              <button key={b.key} type="button" onClick={() => setStatusFilter(active ? '' : key)}
                      className={`text-left rounded-lg border p-3 transition-colors hover:bg-muted/40 ${active ? 'ring-2 ring-primary' : ''} ${b.key === 'current' ? 'border-green-500/30' : 'border-red-500/30'}`}
                      data-testid={`aging-bucket-${b.key}`}>
                <p className="text-xs text-muted-foreground">{b.key === 'current' ? 'Al día (sin vencer)' : `Vencido ${b.label}`}</p>
                <p className={`text-lg font-bold ${b.key === 'current' ? '' : b.balance > 0 ? 'text-red-400' : ''}`}>{formatCurrency(b.balance)}</p>
                <p className="text-xs text-muted-foreground">{b.invoices} factura(s)</p>
              </button>
            );
          })}
          <button type="button" onClick={() => setStatusFilter(statusFilter === 'due_soon' ? '' : 'due_soon')}
                  className={`text-left rounded-lg border border-amber-500/30 p-3 transition-colors hover:bg-muted/40 ${statusFilter === 'due_soon' ? 'ring-2 ring-primary' : ''}`}
                  data-testid="aging-bucket-due-soon">
            <p className="text-xs text-muted-foreground">Por vencer ({aging.due_soon_days} días)</p>
            <p className="text-lg font-bold text-amber-400">{formatCurrency(aging.due_soon_balance)}</p>
            <p className="text-xs text-muted-foreground">{aging.due_soon_invoices} factura(s)</p>
          </button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          «Al día» incluye lo que está por vencer. Los tramos cuentan los días de atraso desde el vencimiento.
        </p>
      </CardContent>
    </Card>
  );
}
