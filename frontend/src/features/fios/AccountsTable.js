import React from 'react';
import { currency as formatCurrency, shortDate } from '@/lib/format';
import StatusBadge from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { ChevronRight, Eye } from 'lucide-react';

// Extraído de Fios.js (mantenimiento fase 5) sin cambios en el JSX.
export default function AccountsTable({ fetchClientDetail, filteredAccounts, searchTerm, statusFilter }) {
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full" data-testid="fios-accounts-table">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium">Cliente</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Total Crédito</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Abonado</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Saldo</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Vencido</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Estado</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Próx. vence</th>
              <th className="px-4 py-3 text-center text-sm font-medium">Facturas</th>
              <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredAccounts.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-muted-foreground">
                  {searchTerm || statusFilter ? 'No se encontraron cuentas con ese filtro' : 'No hay cuentas por cobrar pendientes'}
                </td>
              </tr>
            ) : (
              filteredAccounts.map((account) => (
                <tr key={`${account.client_document_type || ''}-${account.client_document}`} className="hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <div className="font-medium">{account.client_name}</div>
                    <div className="text-xs text-muted-foreground font-mono">
                      {account.client_document_type ? `${account.client_document_type} ` : ''}{account.client_document}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(account.total_credit)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-green-400">
                    {formatCurrency(account.total_paid)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-red-400">
                    {formatCurrency(account.balance)}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${account.overdue_balance > 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                    {account.overdue_balance > 0 ? formatCurrency(account.overdue_balance) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={account.credit_status} label={account.credit_status_label} />
                  </td>
                  <td className="px-4 py-3 text-sm whitespace-nowrap">
                    {shortDate(account.next_due_date)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-1 bg-muted rounded-full text-sm">
                      {account.invoices_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => fetchClientDetail({ number: account.client_document, type: account.client_document_type })}
                      data-testid={`view-client-${account.client_document}`}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      Ver Detalle
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
