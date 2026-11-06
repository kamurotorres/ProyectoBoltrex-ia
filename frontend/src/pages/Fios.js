import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Wallet,
  Search,
  Eye,
  DollarSign,
  User,
  FileText,
  ChevronRight,
  ArrowLeft,
  CreditCard,
  Calendar,
  CheckCircle2,
  Clock,
  Loader2,
  AlertTriangle,
  CalendarClock
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import ExportMenu from '@/components/ExportMenu';
import { API } from '@/App';

// P2.30: estado de una cuenta / factura (al día · por vencer · vencida).
const STATUS_STYLE = {
  overdue: 'bg-red-500/15 text-red-400 border-red-500/30',
  due_soon: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  current: 'bg-green-500/15 text-green-400 border-green-500/30',
};
const StatusBadge = ({ status, label }) => (
  <span className={`inline-block px-2 py-0.5 rounded-full border text-xs whitespace-nowrap ${STATUS_STYLE[status] || STATUS_STYLE.current}`}>
    {label}
  </span>
);
const FILTERS = [
  { key: '', label: 'Todas' },
  { key: 'overdue', label: 'Vencidas' },
  { key: 'due_soon', label: 'Por vencer' },
  { key: 'current', label: 'Sin vencidas' },
];

const Fios = () => {
  // P1.18: cuentas paginadas y buscadas en el servidor; totales de toda la cartera.
  // P2.30: filtro por estado / tramo de antigüedad (clic en las tarjetas de antigüedad).
  const [searchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || '');
  const list = usePaginatedList(`${API}/fios`, {
    params: statusFilter ? { status: statusFilter } : {},
    errorMessage: 'Error al cargar las cuentas por cobrar',
  });
  const accounts = list.items;
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const searchTerm = list.search;
  const setSearchTerm = list.setSearch;
  const [selectedClient, setSelectedClient] = useState(null);
  const [clientDetail, setClientDetail] = useState(null);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [showPaymentDialog, setShowPaymentDialog] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    payment_method: '',
    notes: ''
  });

  const { canCreate, canRead } = usePermissions();
  const moduleSlug = 'fios';

  const fetchAccounts = () => list.reload();
  useEffect(() => {
    if (!list.loading) setLoading(false);
  }, [list.loading]);

  const fetchPaymentMethods = async () => {
    try {
      const response = await axios.get(`${API}/payment-methods/active`);
      setPaymentMethods(response.data);
    } catch (error) {
      console.error('Error fetching payment methods:', error);
    }
  };

  useEffect(() => {
    fetchPaymentMethods();
  }, []);

  // P2.34: la campana de alertas abre Fios filtrado (?status=) o en el detalle de un cliente (?doc=&type=).
  useEffect(() => {
    const status = searchParams.get('status');
    if (status) setStatusFilter(status);
    const doc = searchParams.get('doc');
    if (doc) fetchClientDetail({ number: doc, type: searchParams.get('type') || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // P1.15: la cuenta es por tipo + número de documento ({ number, type }).
  const fetchClientDetail = async (account) => {
    try {
      const response = await axios.get(`${API}/fios/${encodeURIComponent(account.number)}`, {
        params: account.type ? { document_type: account.type } : {},
      });
      setClientDetail(response.data);
      setSelectedClient(account);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al cargar el detalle del cliente'));
      console.error(error);
    }
  };

  const handleBackToList = () => {
    setSelectedClient(null);
    setClientDetail(null);
    fetchAccounts(); // Refresh the list
  };

  const handleOpenPayment = (invoice) => {
    setSelectedInvoice(invoice);
    setPaymentForm({
      amount: invoice.balance.toString(),
      payment_method: '',
      notes: ''
    });
    setShowPaymentDialog(true);
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!paymentForm.amount || parseFloat(paymentForm.amount) <= 0) {
      toast.error('Ingrese un monto válido');
      return;
    }

    if (!paymentForm.payment_method) {
      toast.error('Seleccione una forma de pago');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await axios.post(`${API}/fios/${selectedInvoice.invoice_number}/payment`, {
        amount: parseFloat(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        notes: paymentForm.notes || null
      });

      toast.success(response.data.message);
      notifyDataChanged();
      setShowPaymentDialog(false);

      // Refresh client detail
      if (selectedClient) {
        fetchClientDetail(selectedClient);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al registrar el abono');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('es-CO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  const filteredAccounts = accounts;
  const aging = list.aging || null;
  const shortDate = (dateStr) => (dateStr ? new Date(dateStr).toLocaleDateString('es-CO') : '—');

  // Totales de TODA la cartera, calculados en el servidor (no solo la página visible).
  const s = list.summary || {};
  const totals = {
    total_credit: s.total_credit || 0,
    total_paid: s.total_paid || 0,
    balance: s.balance || 0,
    clients_count: s.clients_count || 0
  };

  if (loading && !selectedClient) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="fios-loading">
        <div className="text-muted-foreground">Cargando...</div>
      </div>
    );
  }

  // Client Detail View
  if (selectedClient && clientDetail) {
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
        <Dialog open={showPaymentDialog} onOpenChange={setShowPaymentDialog}>
          <DialogContent data-testid="payment-dialog-detail">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Registrar Abono
              </DialogTitle>
            </DialogHeader>
            {selectedInvoice && (
              <form onSubmit={handleSubmitPayment} className="space-y-4">
                <div className="p-4 bg-muted/30 rounded-lg space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Factura:</span>
                    <span className="font-mono">{selectedInvoice.invoice_number}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total Factura:</span>
                    <span className="font-mono">{formatCurrency(selectedInvoice.total)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Ya Abonado:</span>
                    <span className="font-mono text-green-400">{formatCurrency(selectedInvoice.amount_paid)}</span>
                  </div>
                  <div className="flex justify-between font-bold border-t border-border pt-2">
                    <span>Saldo Pendiente:</span>
                    <span className="font-mono text-red-400">{formatCurrency(selectedInvoice.balance)}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="amount-detail">Monto a Abonar *</Label>
                  <Input
                    id="amount-detail"
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={selectedInvoice.balance}
                    value={paymentForm.amount}
                    onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                    placeholder="0.00"
                    data-testid="input-payment-amount-detail"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="payment_method-detail">Forma de Pago *</Label>
                  <Select
                    value={paymentForm.payment_method}
                    onValueChange={(value) => setPaymentForm({ ...paymentForm, payment_method: value })}
                  >
                    <SelectTrigger data-testid="select-payment-method-detail">
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
                  <Label htmlFor="notes-detail">Notas (opcional)</Label>
                  <Textarea
                    id="notes-detail"
                    value={paymentForm.notes}
                    onChange={(e) => setPaymentForm({ ...paymentForm, notes: e.target.value })}
                    placeholder="Observaciones del pago..."
                    rows={2}
                    data-testid="input-payment-notes-detail"
                  />
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setShowPaymentDialog(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" disabled={isSubmitting} data-testid="submit-payment-btn-detail">
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
      </div>
    );
  }

  // Main List View
  return (
    <div className="space-y-6" data-testid="fios-page">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" data-testid="fios-title">
          <Wallet className="h-6 w-6" />
          Fios - Cuentas por Cobrar
        </h1>
        <p className="text-muted-foreground mt-1">
          Gestión de créditos y registro de abonos
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Clientes con Crédito</p>
                <p className="text-2xl font-bold">{totals.clients_count}</p>
              </div>
              <User className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Crédito</p>
                <p className="text-2xl font-bold">{formatCurrency(totals.total_credit)}</p>
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
                <p className="text-2xl font-bold text-green-400">{formatCurrency(totals.total_paid)}</p>
              </div>
              <CheckCircle2 className="h-8 w-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-red-500/30">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Saldo Pendiente</p>
                <p className="text-2xl font-bold text-red-400">{formatCurrency(totals.balance)}</p>
              </div>
              <DollarSign className="h-8 w-8 text-red-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* P2.30: antigüedad de la cartera (clic para filtrar) */}
      {aging && (
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
      )}

      {/* Search + filtros + exportar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por cliente o documento..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="fios-search-input"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <Button key={f.key || 'all'} size="sm" variant={statusFilter === f.key ? 'default' : 'outline'}
                    onClick={() => setStatusFilter(f.key)} data-testid={`fios-filter-${f.key || 'all'}`}>
              {f.label}
            </Button>
          ))}
          {statusFilter && !FILTERS.some((f) => f.key === statusFilter) && (
            <Button size="sm" variant="default" onClick={() => setStatusFilter('')}>
              Vencido {aging?.buckets.find((b) => b.key === statusFilter)?.label || statusFilter} ✕
            </Button>
          )}
        </div>
        <ExportMenu url={`${API}/fios/export`} className="ml-auto" fallbackName="cartera" testId="fios-export-button"
                    params={{ ...(statusFilter ? { status: statusFilter } : {}), ...(searchTerm.trim() ? { search: searchTerm.trim() } : {}) }}
                    hint="Cartera completa con el filtro activo y los tramos de antigüedad." />
      </div>

      {/* Accounts Table */}
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
      <Pagination {...list.paginationProps} noun="cuenta(s)" testId="fios-pagination" />

      {/* Payment Dialog */}
      <Dialog open={showPaymentDialog} onOpenChange={setShowPaymentDialog}>
        <DialogContent data-testid="payment-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5" />
              Registrar Abono
            </DialogTitle>
          </DialogHeader>
          {selectedInvoice && (
            <form onSubmit={handleSubmitPayment} className="space-y-4">
              <div className="p-4 bg-muted/30 rounded-lg space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Factura:</span>
                  <span className="font-mono">{selectedInvoice.invoice_number}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Total Factura:</span>
                  <span className="font-mono">{formatCurrency(selectedInvoice.total)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Ya Abonado:</span>
                  <span className="font-mono text-green-400">{formatCurrency(selectedInvoice.amount_paid)}</span>
                </div>
                <div className="flex justify-between font-bold border-t border-border pt-2">
                  <span>Saldo Pendiente:</span>
                  <span className="font-mono text-red-400">{formatCurrency(selectedInvoice.balance)}</span>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="amount">Monto a Abonar *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={selectedInvoice.balance}
                  value={paymentForm.amount}
                  onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                  placeholder="0.00"
                  data-testid="input-payment-amount"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="payment_method">Forma de Pago *</Label>
                <Select
                  value={paymentForm.payment_method}
                  onValueChange={(value) => setPaymentForm({ ...paymentForm, payment_method: value })}
                >
                  <SelectTrigger data-testid="select-payment-method">
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
                <Label htmlFor="notes">Notas (opcional)</Label>
                <Textarea
                  id="notes"
                  value={paymentForm.notes}
                  onChange={(e) => setPaymentForm({ ...paymentForm, notes: e.target.value })}
                  placeholder="Observaciones del pago..."
                  rows={2}
                  data-testid="input-payment-notes"
                />
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowPaymentDialog(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSubmitting} data-testid="submit-payment-btn">
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
    </div>
  );
};

export default Fios;
