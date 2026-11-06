import React, {} from 'react';
import { toast } from 'sonner';
import { money, shortDateTime as when } from '@/lib/format';

// Movido de Cash.js sin cambios (mantenimiento fase 5).
export function SummaryTable({ summary }) {
  if (!summary) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="cash-summary">
        <thead className="text-muted-foreground text-xs">
          <tr>
            <th className="text-left py-2 px-2 font-medium">Forma de pago</th>
            <th className="text-right py-2 px-2 font-medium">Base</th>
            <th className="text-right py-2 px-2 font-medium">Ventas</th>
            <th className="text-right py-2 px-2 font-medium">Abonos</th>
            <th className="text-right py-2 px-2 font-medium">Reembolsos</th>
            <th className="text-right py-2 px-2 font-medium">Ingresos</th>
            <th className="text-right py-2 px-2 font-medium">Egresos</th>
            <th className="text-right py-2 px-2 font-medium">Esperado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border font-mono">
          {summary.methods.map((m) => (
            <tr key={m.method} className={m.is_cash ? 'font-semibold' : ''}>
              <td className="py-2 px-2 font-sans">{m.method}</td>
              <td className="py-2 px-2 text-right">{m.is_cash ? money(m.opening) : '—'}</td>
              <td className="py-2 px-2 text-right">{money(m.sales)}</td>
              <td className="py-2 px-2 text-right">{money(m.fio_payments)}</td>
              <td className="py-2 px-2 text-right">{m.refunds ? `−${money(m.refunds)}` : money(0)}</td>
              <td className="py-2 px-2 text-right">{money(m.income)}</td>
              <td className="py-2 px-2 text-right">{m.expense ? `−${money(m.expense)}` : money(0)}</td>
              <td className="py-2 px-2 text-right">{money(m.expected)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground mt-2">
        Efectivo esperado = base + ventas + abonos + ingresos − reembolsos − egresos (solo efectivo).
      </p>
    </div>
  );
}

export function Movements({ movements }) {
  if (!movements?.length) return <p className="text-sm text-muted-foreground py-4">Sin movimientos todavía.</p>;
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="text-left py-1.5 px-2 font-medium">Hora</th>
            <th className="text-left py-1.5 px-2 font-medium">Tipo</th>
            <th className="text-left py-1.5 px-2 font-medium">Forma de pago</th>
            <th className="text-left py-1.5 px-2 font-medium">Referencia / motivo</th>
            <th className="text-right py-1.5 px-2 font-medium">Monto</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {movements.map((m, i) => (
            <tr key={i}>
              <td className="py-1.5 px-2 whitespace-nowrap">{when(m.created_at)}</td>
              <td className="py-1.5 px-2">{m.kind_label}{m.attached_on_open ? ' (pendiente)' : ''}</td>
              <td className="py-1.5 px-2">{m.method}</td>
              <td className="py-1.5 px-2">{m.reference || m.reason || '—'}</td>
              <td className="py-1.5 px-2 text-right font-mono">{m.direction === 'out' ? '−' : '+'}{money(m.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Reporte de cierre imprimible en ticket de 80 mm.
export function printReport(s) {
  const rows = (s.summary?.methods || []).map((m) => `<tr><td>${m.method}</td><td class="r">${money(m.expected)}</td></tr>`).join('');
  const denoms = Object.entries(s.denominations || {}).sort((a, b) => b[0] - a[0])
    .map(([d, q]) => `<tr><td>${q} × ${money(d)}</td><td class="r">${money(d * q)}</td></tr>`).join('');
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Cierre ${s.session_id}</title>
  <style>@page{size:80mm auto;margin:4mm}body{font:12px monospace;width:72mm;margin:0}h1{font-size:14px;text-align:center;margin:0 0 6px}
  table{width:100%;border-collapse:collapse}td{padding:2px 0}.r{text-align:right}hr{border:0;border-top:1px dashed #000;margin:6px 0}</style></head><body>
  <h1>CIERRE DE CAJA ${s.session_id}</h1>
  <div>Cajero: ${s.cashier_name || s.cashier_email}</div><div>Apertura: ${when(s.opened_at)}</div><div>Cierre: ${when(s.closed_at)}</div>
  ${s.forced_close ? `<div>Cerrada por: ${s.closed_by} (forzado)</div>` : ''}<hr>
  <div><b>Esperado por forma de pago</b></div><table>${rows}</table><hr>
  <table><tr><td>Base inicial</td><td class="r">${money(s.opening_amount)}</td></tr>
  <tr><td>Efectivo esperado</td><td class="r">${money(s.summary?.expected_cash)}</td></tr>
  <tr><td>Efectivo contado</td><td class="r">${money(s.counted_cash)}</td></tr>
  <tr><td><b>Diferencia</b></td><td class="r"><b>${s.difference > 0 ? '+' : ''}${money(s.difference)}</b></td></tr></table>
  ${denoms ? `<hr><div><b>Arqueo</b></div><table>${denoms}</table>` : ''}
  ${s.closing_notes ? `<hr><div>Obs.: ${s.closing_notes}</div>` : ''}
  <hr><div style="text-align:center">Firma cajero: ____________</div></body></html>`;
  const w = window.open('', '_blank', 'width=420,height=640');
  if (!w) {
    toast.error('El navegador bloqueó la ventana de impresión: permite las ventanas emergentes para Boltrex.');
    return;
  }
  w.document.write(html);
  w.document.close();
  w.focus();
  w.print();
}

export default SummaryTable;
