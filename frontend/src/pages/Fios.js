import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Wallet
} from 'lucide-react';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';
import PaymentDialog from '@/components/fios/PaymentDialog';
import ClientDetail from '@/features/fios/ClientDetail';
import SummaryCards from '@/features/fios/SummaryCards';
import AgingCard from '@/features/fios/AgingCard';
import FiltersBar from '@/features/fios/FiltersBar';
import AccountsTable from '@/features/fios/AccountsTable';

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
      const response = await api.get(`/payment-methods/active`);
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
      const response = await api.get(`/fios/${encodeURIComponent(account.number)}`, {
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
      const response = await api.post(`/fios/${selectedInvoice.invoice_number}/payment`, {
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
      toast.error(getErrorMessage(error, 'Error al registrar el abono'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredAccounts = accounts;
  const aging = list.aging || null;

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
      <ClientDetail canCreate={canCreate} clientDetail={clientDetail} handleBackToList={handleBackToList} handleOpenPayment={handleOpenPayment} handleSubmitPayment={handleSubmitPayment} isSubmitting={isSubmitting} moduleSlug={moduleSlug} paymentForm={paymentForm} paymentMethods={paymentMethods} selectedInvoice={selectedInvoice} setPaymentForm={setPaymentForm} setShowPaymentDialog={setShowPaymentDialog} showPaymentDialog={showPaymentDialog} />
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
      <SummaryCards totals={totals} />

      {/* P2.30: antigüedad de la cartera (clic para filtrar) */}
      {aging && (
        <AgingCard aging={aging} setStatusFilter={setStatusFilter} statusFilter={statusFilter} />
      )}

      {/* Search + filtros + exportar */}
      <FiltersBar aging={aging} searchTerm={searchTerm} setSearchTerm={setSearchTerm} setStatusFilter={setStatusFilter} statusFilter={statusFilter} />

      {/* Accounts Table */}
      <AccountsTable fetchClientDetail={fetchClientDetail} filteredAccounts={filteredAccounts} searchTerm={searchTerm} statusFilter={statusFilter} />
      <Pagination {...list.paginationProps} noun="cuenta(s)" testId="fios-pagination" />

      {/* Payment Dialog */}
      <PaymentDialog open={showPaymentDialog} onOpenChange={setShowPaymentDialog} invoice={selectedInvoice}
                     form={paymentForm} setForm={setPaymentForm} paymentMethods={paymentMethods}
                     isSubmitting={isSubmitting} onSubmit={handleSubmitPayment} />
    </div>
  );
};

export default Fios;
