import React from 'react';
import { Button } from '@/components/ui/button';
import { ArrowLeft, CheckCircle2, Clock, DollarSign, FileText, User } from 'lucide-react';
import ExportMenu from '@/components/ExportMenu';
import { API } from '@/api/client';
import { currency as formatCurrency, dateTime as formatDate, shortDate } from '@/lib/format';
import { Card, CardContent } from '@/components/ui/card';
import StatusBadge from '@/components/StatusBadge';
import PaymentDialog from '@/components/fios/PaymentDialog';

// Extraído de Fios.js (mantenimiento fase 5) sin cambios en el JSX.
export default function ClientDetail({ canCreate, clientDetail, handleBackToList, handleOpenPayment, handleSubmitPayment, isSubmitting, moduleSlug, paymentForm, paymentMethods, selectedInvoice, setPaymentForm, setShowPaymentDialog, showPaymentDialog }) {
  return (
    <div className="space-y-6" data-testid="fios-client-detail">
      {/* Back Button */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <Button variant="ghost" onClick={handleBackToList}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver al listado
        </Button>
        {/* P2.33: estado de cuenta para enviarle al cliente (pendiente + abonos) */}
        <ExportMenu url={`${API}/fios/statement/${encodeURIComponent(clientDetail.client.document_number)}`}
                    params={clientDetail.client.document_type ? { document_type: clientDetail.client.document_type } : {}}
                    formats={['pdf', 'xlsx']} label="Estado de cuenta" variant="default" fallbackName="estado_cuenta"
                    testId="fios-statement-button" hint="Facturas pendientes con su vencimiento, abonos y saldo." />
      </div>

      {/* Client Info */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold flex items-center gap-2">
              <User className="h-5 w-5" />
              {clientDetail.client.name}
            </h2>
            <p className="text-muted-foreground font-mono">
              {clientDetail.client.document_type ? `${clientDetail.client.document_type} ` : ''}{clientDetail.client.document_number}
            </p>
            {clientDetail.client.phone && (
              <p className="text-sm text-muted-foreground mt-1">
                Tel: {clientDetail.client.phone}
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">Saldo Pendiente</p>
            <p className="text-2xl font-bold text-red-400">
              {formatCurrency(clientDetail.summary.balance)}
            </p>
            {clientDetail.summary.overdue_balance > 0 && (
              <p className="text-sm text-red-400 mt-1" data-testid="fios-detail-overdue">
                Vencido: {formatCurrency(clientDetail.summary.overdue_balance)} · {clientDetail.summary.max_days_overdue} día(s) de atraso
              </p>
            )}
            {clientDetail.credit && (
              <p className="text-xs text-muted-foreground mt-1">
                Plazo {clientDetail.credit.term_days} día(s)
                {clientDetail.credit.credit_limit
                  ? ` · cupo ${formatCurrency(clientDetail.credit.credit_limit)} (disponible ${formatCurrency(Math.max(0, clientDetail.credit.available))})`
                  : ' · sin cupo límite'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Crédito</p>
                <p className="text-xl font-bold">{formatCurrency(clientDetail.summary.total_credit)}</p>
              </div>
              <FileText className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Abonado</p>
                <p className="text-xl font-bold text-green-400">{formatCurrency(clientDetail.summary.total_paid)}</p>
              </div>
              <CheckCircle2 className="h-8 w-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Facturas Pendientes</p>
                <p className="text-xl font-bold">{clientDetail.summary.invoices_count}</p>
              </div>
              <Clock className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pending Invoices */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="font-semibold">Facturas Pendientes</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">Factura</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Fecha</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Vence</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Estado</th>
                <th className="px-4 py-3 text-right text-sm font-medium">Total</th>
                <th className="px-4 py-3 text-right text-sm font-medium">Abonado</th>
                <th className="px-4 py-3 text-right text-sm font-medium">Saldo</th>
                <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {clientDetail.invoices.map((invoice) => (
                <tr key={invoice.invoice_number} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-mono text-sm">
                    {invoice.invoice_number}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatDate(invoice.created_at)}
                  </td>
                  <td className="px-4 py-3 text-sm whitespace-nowrap">
                    {shortDate(invoice.due_date)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={invoice.credit_status} label={invoice.credit_status_label} />
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(invoice.total)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-green-400">
                    {formatCurrency(invoice.amount_paid)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-red-400">
                    {formatCurrency(invoice.balance)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {canCreate(moduleSlug) && (
                      <Button
                        size="sm"
                        onClick={() => handleOpenPayment(invoice)}
                        data-testid={`pay-invoice-${invoice.invoice_number}`}
                      >
                        <DollarSign className="h-4 w-4 mr-1" />
                        Abonar
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment History */}
      {clientDetail.payment_history.length > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="font-semibold">Historial de Abonos</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">ID Pago</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Factura</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Fecha</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Forma de Pago</th>
                  <th className="px-4 py-3 text-right text-sm font-medium">Monto</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Notas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {clientDetail.payment_history.map((payment) => (
                  <tr key={payment.payment_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-mono text-sm">
                      {payment.payment_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-sm">
                      {payment.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatDate(payment.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="px-2 py-1 bg-primary/20 text-primary rounded">
                        {payment.payment_method}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-green-400">
                      {formatCurrency(payment.amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {payment.notes || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Payment Dialog for Detail View */}
      <PaymentDialog open={showPaymentDialog} onOpenChange={setShowPaymentDialog} invoice={selectedInvoice}
                     form={paymentForm} setForm={setPaymentForm} paymentMethods={paymentMethods}
                     isSubmitting={isSubmitting} onSubmit={handleSubmitPayment} suffix="-detail" />
    </div>
  );
}
