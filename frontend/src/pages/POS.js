import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { api } from '@/api/client';
import { useServerSearch } from '@/hooks/useServerSearch';
import { useCart, useCashState, useCreditStatus } from '@/features/pos/usePosState';
import { priceFor } from '@/features/pos/cart';
import ClientSection from '@/features/pos/ClientSection';
import ProductSection from '@/features/pos/ProductSection';
import CartSection from '@/features/pos/CartSection';
import { shortDate } from '@/lib/format';

const POS = () => {
  const { canCreate } = usePermissions();
  // Mantenimiento fase 5: carrito, cupo/vencimiento y caja en features/pos/usePosState.js;
  // reglas del carrito en features/pos/cart.js (probadas contra el original en tests/frontend_cart_check.js).
  const { cart, setCart, rememberProducts, addToCart: addLine, updateQuantity, setQuantity, removeFromCart, repriceFor, clearCart,
          totals } = useCart();
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [searchProduct, setSearchProduct] = useState('');
  const [searchClient, setSearchClient] = useState('');
  const [selectedClient, setSelectedClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  // Payment fields
  const [paymentStatus, setPaymentStatus] = useState('pagado');
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('');
  // P2.30: estado de crédito del cliente (saldo, vencido, cupo) y vencimiento de la venta a crédito.
  const { creditStatus, dueDate, setDueDate } = useCreditStatus(selectedClient);
  // P2.31: caja exigida / abierta.
  const { cashState, fetchCashState } = useCashState();

  // P1.18: productos y clientes se buscan en el servidor mientras se escribe (sin tope oculto).
  const { results: filteredProducts, searching: searchingProducts } = useServerSearch('/products', searchProduct, {
    errorMessage: 'Error al buscar productos', onResults: rememberProducts,   // se guardan para recalcular el carrito
  });
  const { results: filteredClients, searching: searchingClients } = useServerSearch('/clients', searchClient, {
    errorMessage: 'Error al buscar clientes',
  });

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    fetchCashState();
    try {
      const [paymentMethodsRes] = await Promise.all([
        api.get(`/payment-methods/active`)
      ]);
      setPaymentMethods(paymentMethodsRes.data);

      if (paymentMethodsRes.data.length > 0) {
        setSelectedPaymentMethod(paymentMethodsRes.data[0].name);
      }
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  // P1.17: precio de la lista del cliente; si el producto no la tiene, el de 'default' (features/pos/cart.js).
  const getProductPrice = (product) => priceFor(product, selectedClient && selectedClient.price_list);
  const addToCart = (product) => {
    if (addLine(product, selectedClient)) setSearchProduct('');   // Clear search after adding
  };

  const downloadTicket = async (invoiceNumber) => {
    try {
      const response = await api.get(`/pos/invoices/${invoiceNumber}/ticket`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ticket_${invoiceNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading ticket:', error);
    }
  };

  const handleCheckout = async () => {
    if (isProcessing) return;

    if (!selectedClient) {
      toast.error('Selecciona un cliente');
      return;
    }
    if (cart.length === 0) {
      toast.error('El carrito está vacío');
      return;
    }

    if (paymentStatus === 'pagado' && !selectedPaymentMethod) {
      toast.error('Selecciona una forma de pago');
      return;
    }

    setIsProcessing(true);
    try {
      const invoiceData = {
        client_document: selectedClient.document_number,
        client_document_type: selectedClient.document_type,   // P1.15
        items: cart,
        payment_status: paymentStatus,
        payment_method: paymentStatus === 'pagado' ? selectedPaymentMethod : null,
        // P2.30: vencimiento elegido (vacío = plazo del cliente o el de Config. Sistema).
        due_date: paymentStatus === 'por_cobrar' ? (dueDate || null) : null,
        tz_offset_minutes: new Date().getTimezoneOffset()
      };

      const response = await api.post(`/invoices`, invoiceData);

      const statusMessage = paymentStatus === 'pagado'
        ? `Factura ${response.data.invoice_number} creada - PAGADA con ${selectedPaymentMethod}`
        : `Factura ${response.data.invoice_number} creada - POR COBRAR${response.data.due_date ? ` · vence el ${shortDate(response.data.due_date)}` : ''}`;

      toast.success(statusMessage, {
        action: paymentStatus === 'pagado' ? {
          label: 'Descargar Ticket',
          onClick: () => downloadTicket(response.data.invoice_number)
        } : undefined,
        duration: 5000
      });

      if (paymentStatus === 'pagado') {
        setTimeout(() => downloadTicket(response.data.invoice_number), 500);
      }
      // P2.34: lo que quedó en bajo stock o agotado con esta venta.
      const warnings = response.data.stock_warnings || [];
      if (warnings.length) {
        const text = warnings.slice(0, 4).map((w) => (w.status === 'out'
          ? `${w.name}: AGOTADO`
          : `${w.name} quedó con ${w.stock} unidad(es) (mínimo ${w.min_stock})`)).join(' · ');
        toast.warning(`Stock bajo: ${text}${warnings.length > 4 ? ` y ${warnings.length - 4} más` : ''}`, { duration: 8000 });
      }
      notifyDataChanged();

      clearCart();
      setSelectedClient(null);
      setSearchClient('');
      setSearchProduct('');
      setPaymentStatus('pagado');
      setDueDate('');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al crear factura'));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClientChange = (client) => {
    // P1.15: el cliente es tipo + número. P1.17: precio de su lista o el 'default'.
    const sameClient = selectedClient && selectedClient.document_number === client.document_number
      && selectedClient.document_type === client.document_type;
    if (cart.length > 0 && selectedClient && !sameClient) {
      repriceFor(client);
    }
    setSelectedClient(client);
    setSearchClient('');
  };

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="pos-page" className="space-y-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Punto de Venta (POS)</h1>
        <p className="text-muted-foreground mt-2">Sistema de facturación rápida</p>
      </div>

      {cashState.required && !cashState.open && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm" role="alert" data-testid="pos-cash-required">
          <span><span className="font-semibold">Abre tu caja antes de vender.</span> La configuración del sistema exige una caja abierta.</span>
          <Link to="/cash" className="underline underline-offset-2">Ir a Caja</Link>
        </div>
      )}

      {/* SECTION 1: Client Selection - Full Width */}
      <ClientSection creditStatus={creditStatus} filteredClients={filteredClients} handleClientChange={handleClientChange} searchClient={searchClient} searchingClients={searchingClients} selectedClient={selectedClient} setSearchClient={setSearchClient} setSelectedClient={setSelectedClient} />

      {/* SECTION 2: Product Search - Full Width */}
      <ProductSection addToCart={addToCart} cart={cart} filteredProducts={filteredProducts} getProductPrice={getProductPrice} searchProduct={searchProduct} searchingProducts={searchingProducts} selectedClient={selectedClient} setSearchProduct={setSearchProduct} />

      {/* SECTION 3: Cart and Checkout - Full Width */}
      <CartSection canCreate={canCreate} cart={cart} cashState={cashState} creditStatus={creditStatus} dueDate={dueDate} handleCheckout={handleCheckout} isProcessing={isProcessing} paymentMethods={paymentMethods} paymentStatus={paymentStatus} removeFromCart={removeFromCart} selectedClient={selectedClient} selectedPaymentMethod={selectedPaymentMethod} setCart={setCart} setDueDate={setDueDate} setPaymentStatus={setPaymentStatus} setQuantity={setQuantity} setSelectedPaymentMethod={setSelectedPaymentMethod} totals={totals} updateQuantity={updateQuantity} />
    </div>
  );
};

export default POS;
