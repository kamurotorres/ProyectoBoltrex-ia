import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, Minus, Plus, Trash2, ShoppingCart, CreditCard, Wallet, User, AlertCircle, AlertTriangle, Package, Loader2, CalendarClock } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { money as money0, ymdToDmy as dmy } from '@/lib/format';
import { api } from '@/api/client';

// P2.30: fechas locales AAAA-MM-DD para el vencimiento de las ventas a crédito.
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const addDays = (days) => { const d = new Date(); d.setDate(d.getDate() + Number(days || 0)); return ymd(d); };

const POS = () => {
  const { canCreate } = usePermissions();
  // P1.18: productos y clientes se buscan en el servidor mientras se escribe (sin tope oculto).
  // `products` guarda los productos vistos (resultados y carrito) para recalcular el carrito.
  const [products, setProducts] = useState([]);
  const [productResults, setProductResults] = useState([]);
  const [clientResults, setClientResults] = useState([]);
  const [searchingProducts, setSearchingProducts] = useState(false);
  const [searchingClients, setSearchingClients] = useState(false);
  const productReq = useRef(0);
  const clientReq = useRef(0);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [searchProduct, setSearchProduct] = useState('');
  const [searchClient, setSearchClient] = useState('');
  const [selectedClient, setSelectedClient] = useState(null);
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  // Payment fields
  const [paymentStatus, setPaymentStatus] = useState('pagado');
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('');
  // P2.30: estado de crédito del cliente (saldo, vencido, cupo) y vencimiento de la venta a crédito.
  const [creditStatus, setCreditStatus] = useState(null);
  const [dueDate, setDueDate] = useState('');
  useEffect(() => {
    setCreditStatus(null);
    if (!selectedClient) return undefined;
    let cancelled = false;
    api.get(`/credit/client-status`, {
      params: { document_number: selectedClient.document_number, document_type: selectedClient.document_type },
    }).then((r) => {
      if (cancelled) return;
      setCreditStatus(r.data);
      setDueDate(addDays(r.data.term_days));
    }).catch(() => { if (!cancelled) setCreditStatus(null); });
    return () => { cancelled = true; };
  }, [selectedClient]);

  useEffect(() => {
    fetchData();
  }, []);

  // P2.31: si la configuración exige caja abierta, el POS avisa y bloquea el cobro sin ella
  // (el backend lo exige igual).
  const [cashState, setCashState] = useState({ required: false, open: true });
  const fetchCashState = async () => {
    try {
      const [settingsRes, currentRes] = await Promise.all([
        api.get(`/cash/settings`),
        api.get(`/cash/current`).catch(() => ({ data: { session: null } })),
      ]);
      setCashState({ required: !!settingsRes.data.require_open_session, open: !!currentRes.data.session });
    } catch {
      setCashState({ required: false, open: true });
    }
  };

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

  // P1.17: precio de la lista del cliente; si el producto no la tiene, el de 'default'.
  // Sin ninguno de los dos el producto no se puede vender (antes se inventaba costo × 1,3).
  const getProductPrice = (product) => {
    const prices = product.prices || [];
    const pick = (name) => prices.find((p) => p.price_list_name === name);
    const found = (selectedClient && pick(selectedClient.price_list)) || pick('default');
    return found ? found.price : null;
  };

  const addToCart = (product) => {
    if (!selectedClient) {
      toast.error('Primero selecciona un cliente');
      return;
    }
    if (getProductPrice(product) === null) {
      toast.error(`El producto '${product.name}' no tiene precio de venta. Agrégale un precio en Productos.`);
      return;
    }

    if (product.stock <= 0) {
      toast.error('Producto sin stock');
      return;
    }

    const existingItemIndex = cart.findIndex(item => item.barcode === product.barcode);

    if (existingItemIndex !== -1) {
      const existingItem = cart[existingItemIndex];
      const newQuantity = existingItem.quantity + 1;

      if (newQuantity > product.stock) {
        toast.error('Stock insuficiente');
        return;
      }

      const subtotal = existingItem.unit_price * newQuantity;
      const taxAmount = (subtotal * existingItem.tax_rate) / 100;
      const total = subtotal + taxAmount;

      setCart(cart.map((item, index) =>
        index === existingItemIndex
          ? { ...item, quantity: newQuantity, subtotal, tax_amount: taxAmount, total }
          : item
      ));
    } else {
      const unitPrice = getProductPrice(product);
      const subtotal = unitPrice;
      const taxAmount = (subtotal * product.tax_rate) / 100;
      const total = subtotal + taxAmount;

      setCart([...cart, {
        barcode: product.barcode,
        product_name: product.name,
        quantity: 1,
        unit_price: unitPrice,
        tax_rate: product.tax_rate,
        subtotal,
        tax_amount: taxAmount,
        total
      }]);
    }

    // Clear search after adding
    setSearchProduct('');
  };

  const updateQuantity = (barcode, delta) => {
    const product = products.find(p => p.barcode === barcode);
    setCart(cart.map(item => {
      if (item.barcode === barcode) {
        const newQuantity = item.quantity + delta;
        if (newQuantity <= 0) return item;
        if (newQuantity > product.stock) {
          toast.error('Stock insuficiente');
          return item;
        }
        const subtotal = item.unit_price * newQuantity;
        const taxAmount = (subtotal * item.tax_rate) / 100;
        const total = subtotal + taxAmount;
        return { ...item, quantity: newQuantity, subtotal, tax_amount: taxAmount, total };
      }
      return item;
    }));
  };

  const setQuantity = (barcode, value) => {
    const product = products.find(p => p.barcode === barcode);
    const qty = parseInt(value) || 0;
    if (qty <= 0) return;
    if (product && qty > product.stock) {
      toast.error('Stock insuficiente');
      return;
    }
    setCart(cart.map(item => {
      if (item.barcode === barcode) {
        const subtotal = item.unit_price * qty;
        const taxAmount = (subtotal * item.tax_rate) / 100;
        const total = subtotal + taxAmount;
        return { ...item, quantity: qty, subtotal, tax_amount: taxAmount, total };
      }
      return item;
    }));
  };

  const removeFromCart = (barcode) => {
    setCart(cart.filter(item => item.barcode !== barcode));
  };

  const calculateTotals = () => {
    const subtotal = cart.reduce((sum, item) => sum + item.subtotal, 0);
    const totalTax = cart.reduce((sum, item) => sum + item.tax_amount, 0);
    const total = cart.reduce((sum, item) => sum + item.total, 0);
    return { subtotal, totalTax, total };
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
        : `Factura ${response.data.invoice_number} creada - POR COBRAR${response.data.due_date ? ` · vence el ${new Date(response.data.due_date).toLocaleDateString('es-CO')}` : ''}`;

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

      setCart([]);
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
      const updatedCart = cart.map(item => {
        const product = products.find(p => p.barcode === item.barcode);
        if (product) {
          const prices = product.prices || [];
          const found = prices.find(p => p.price_list_name === client.price_list) || prices.find(p => p.price_list_name === 'default');
          const unitPrice = found ? found.price : item.unit_price;
          const subtotal = unitPrice * item.quantity;
          const taxAmount = (subtotal * item.tax_rate) / 100;
          const total = subtotal + taxAmount;
          return { ...item, unit_price: unitPrice, subtotal, tax_amount: taxAmount, total };
        }
        return item;
      });
      setCart(updatedCart);
    }
    setSelectedClient(client);
    setSearchClient('');
  };

  // Búsqueda de productos en el servidor (desde 2 caracteres, 300 ms tras dejar de escribir).
  useEffect(() => {
    const text = searchProduct.trim();
    if (text.length < 2) {
      setProductResults([]);
      return undefined;
    }
    const id = ++productReq.current;
    setSearchingProducts(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/products`, { params: { search: text, page_size: 20 } });
        if (id !== productReq.current) return;
        const found = res.data.items || [];
        setProductResults(found);
        // Se guardan para recalcular precios del carrito (cambio de cliente, cantidades).
        setProducts((prev) => {
          const map = new Map(prev.map((p) => [p.barcode, p]));
          found.forEach((p) => map.set(p.barcode, p));
          return Array.from(map.values());
        });
      } catch (error) {
        if (id === productReq.current) toast.error(getErrorMessage(error, 'Error al buscar productos'));
      } finally {
        if (id === productReq.current) setSearchingProducts(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchProduct]);

  // Búsqueda de clientes en el servidor.
  useEffect(() => {
    const text = searchClient.trim();
    if (text.length < 2) {
      setClientResults([]);
      return undefined;
    }
    const id = ++clientReq.current;
    setSearchingClients(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/clients`, { params: { search: text, page_size: 20 } });
        if (id === clientReq.current) setClientResults(res.data.items || []);
      } catch (error) {
        if (id === clientReq.current) toast.error(getErrorMessage(error, 'Error al buscar clientes'));
      } finally {
        if (id === clientReq.current) setSearchingClients(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchClient]);

  const filteredProducts = searchProduct.trim().length >= 2 ? productResults : [];
  const filteredClients = searchClient.trim().length >= 2 ? clientResults : [];

  const totals = calculateTotals();

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
      <Card className={`w-full ${!selectedClient ? 'border-orange-500/50 bg-orange-500/5' : 'border-green-500/50 bg-green-500/5'}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <User className="h-5 w-5" />
            1. Seleccionar Cliente
            <span className="text-xs text-orange-500 font-normal">(Requerido)</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {selectedClient ? (
            <div className="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                  <User className="h-6 w-6 text-green-500" />
                </div>
                <div>
                  <p className="font-semibold text-lg">{`${selectedClient.first_name} ${selectedClient.last_name}`}</p>
                  <p className="text-sm text-muted-foreground font-mono">{selectedClient.document_number}</p>
                  {selectedClient.price_list && (
                    <p className="text-xs text-green-400">Lista de precios: {selectedClient.price_list}</p>
                  )}
                  {creditStatus && creditStatus.balance > 0 && (
                    <p className="text-xs text-muted-foreground" data-testid="pos-client-balance">
                      Debe {money0(creditStatus.balance)} en Fios
                      {creditStatus.credit_limit ? ` · cupo disponible ${money0(creditStatus.available)} de ${money0(creditStatus.credit_limit)}` : ''}
                    </p>
                  )}
                  {creditStatus && !creditStatus.balance && creditStatus.credit_limit && (
                    <p className="text-xs text-muted-foreground">Cupo de crédito {money0(creditStatus.credit_limit)}</p>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedClient(null);
                  setSearchClient('');
                }}
              >
                Cambiar Cliente
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/30 rounded-md">
                <AlertCircle className="h-5 w-5 text-orange-400" />
                <p className="text-sm text-orange-400">Busca y selecciona un cliente para continuar con la venta</p>
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Buscar cliente por nombre o documento... (mínimo 2 caracteres)"
                  value={searchClient}
                  onChange={(e) => setSearchClient(e.target.value)}
                  className="pl-10 text-lg h-12"
                  data-testid="pos-search-client-input"
                />
              </div>

              {/* Show clients only when searching */}
              {searchClient.length >= 2 && (
                <div className="border rounded-lg overflow-hidden">
                  {filteredClients.length > 0 ? (
                    <div className="divide-y">
                      {filteredClients.map((client, index) => (
                        <div
                          key={client.document_number}
                          className="flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all"
                          onClick={() => handleClientChange(client)}
                          data-testid={`pos-client-${index}`}
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                              <User className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <p className="font-medium">{`${client.first_name} ${client.last_name}`}</p>
                              <p className="text-sm text-muted-foreground font-mono">{client.document_number}</p>
                            </div>
                          </div>
                          <div className="text-right mr-4">
                            {client.price_list && (
                              <p className="text-sm text-primary">Lista: {client.price_list}</p>
                            )}
                            {client.phone && (
                              <p className="text-xs text-muted-foreground">{client.phone}</p>
                            )}
                          </div>
                          <Button size="sm">
                            Seleccionar
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-muted-foreground">
                      <User className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>{searchingClients ? 'Buscando…' : `No se encontraron clientes para "${searchClient}"`}</p>
                    </div>
                  )}
                </div>
              )}

              {searchClient.length > 0 && searchClient.length < 2 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Escribe al menos 2 caracteres para buscar clientes
                </p>
              )}
            </div>
          )}
          {/* P2.30 (opción A): con facturas vencidas solo se avisa; la venta se permite. */}
          {selectedClient && creditStatus && creditStatus.overdue_balance > 0 && (
            <div className="mt-3 p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-sm text-red-400 flex items-start gap-2" data-testid="pos-overdue-warning">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                Este cliente tiene <strong>{money0(creditStatus.overdue_balance)}</strong> vencidos en {creditStatus.overdue_invoices} factura(s)
                (la más atrasada: {creditStatus.max_days_overdue} día(s)). Puedes venderle, pero conviene cobrarle antes de fiarle más.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* SECTION 2: Product Search - Full Width */}
      <Card className={`w-full ${!selectedClient ? 'opacity-50 pointer-events-none' : ''}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Package className="h-5 w-5" />
            2. Agregar Productos
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar producto por nombre o código de barras... (mínimo 2 caracteres)"
              value={searchProduct}
              onChange={(e) => setSearchProduct(e.target.value)}
              className="pl-10 text-lg h-12"
              disabled={!selectedClient}
              data-testid="pos-search-product-input"
            />
          </div>

          {/* Show products only when searching */}
          {searchProduct.length >= 2 && (
            <div className="border rounded-lg overflow-hidden">
              {filteredProducts.length > 0 ? (
                <div className="divide-y">
                  {filteredProducts.map((product, index) => {
                    const price = getProductPrice(product);
                    const inCart = cart.find(item => item.barcode === product.barcode);

                    return (
                      <div
                        key={product.barcode}
                        className={`flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all ${
                          inCart ? 'bg-green-500/5' : ''
                        }`}
                        onClick={() => addToCart(product)}
                        data-testid={`pos-product-${index}`}
                      >
                        <div className="flex-1">
                          <p className="font-semibold">{product.name}</p>
                          <p className="text-sm text-muted-foreground font-mono">{product.barcode}</p>
                        </div>
                        <div className="text-right mr-4">
                          {price === null ? (
                            <p className="text-sm font-semibold text-red-500">Sin precio de venta</p>
                          ) : (
                            <p className="font-bold text-lg font-mono text-primary">
                              ${price.toLocaleString()}
                            </p>
                          )}
                          <p className={`text-xs ${product.stock > 0 ? 'text-muted-foreground' : 'text-red-500'}`}>
                            Stock: {product.stock}
                          </p>
                        </div>
                        {inCart && (
                          <div className="px-3 py-1 bg-green-500/20 text-green-500 rounded-full text-sm font-medium">
                            En carrito: {inCart.quantity}
                          </div>
                        )}
                        <Button size="sm" className="ml-4">
                          <Plus className="h-4 w-4 mr-1" />
                          Agregar
                        </Button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-8 text-center text-muted-foreground">
                  <Package className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>{searchingProducts ? 'Buscando…' : `No se encontraron productos para "${searchProduct}"`}</p>
                </div>
              )}
            </div>
          )}

          {searchProduct.length > 0 && searchProduct.length < 2 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              Escribe al menos 2 caracteres para buscar productos
            </p>
          )}
        </CardContent>
      </Card>

      {/* SECTION 3: Cart and Checkout - Full Width */}
      <Card className="w-full">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            3. Carrito de Compra
            {cart.length > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-primary text-primary-foreground rounded-full text-sm">
                {cart.length} items
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {cart.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <ShoppingCart className="h-16 w-16 mx-auto mb-4 opacity-30" />
              <p className="text-lg">El carrito está vacío</p>
              <p className="text-sm">Busca y agrega productos para comenzar</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Cart Items Table */}
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium">Producto</th>
                      <th className="px-4 py-3 text-right text-sm font-medium">Precio Unit.</th>
                      <th className="px-4 py-3 text-center text-sm font-medium">Cantidad</th>
                      <th className="px-4 py-3 text-right text-sm font-medium">Subtotal</th>
                      <th className="px-4 py-3 text-right text-sm font-medium">IVA</th>
                      <th className="px-4 py-3 text-right text-sm font-medium">Total</th>
                      <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {cart.map((item, index) => (
                      <tr key={item.barcode} data-testid={`cart-item-${index}`}>
                        <td className="px-4 py-3">
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs text-muted-foreground font-mono">{item.barcode}</p>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          ${item.unit_price.toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => updateQuantity(item.barcode, -1)}
                            >
                              <Minus className="h-4 w-4" />
                            </Button>
                            <input
                              type="number"
                              min="1"
                              className="w-16 text-center font-mono font-bold bg-transparent border rounded-md h-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                              value={item.quantity}
                              onFocus={(e) => e.target.select()}
                              onChange={(e) => {
                                const val = e.target.value;
                                if (val === '') {
                                  setCart(cart.map(ci => ci.barcode === item.barcode ? { ...ci, quantity: '' } : ci));
                                } else {
                                  setQuantity(item.barcode, val);
                                }
                              }}
                              onBlur={(e) => {
                                if (!e.target.value || parseInt(e.target.value) <= 0) {
                                  setQuantity(item.barcode, 1);
                                }
                              }}
                              data-testid={`cart-quantity-input-${item.barcode}`}
                            />
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => updateQuantity(item.barcode, 1)}
                            >
                              <Plus className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          ${item.subtotal.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm text-muted-foreground">
                          ${item.tax_amount.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-bold">
                          ${item.total.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => removeFromCart(item.barcode)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals and Payment */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Payment Options */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Wallet className="h-4 w-4" />
                      Estado de Pago
                    </Label>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        type="button"
                        variant={paymentStatus === 'pagado' ? 'default' : 'outline'}
                        className={`w-full h-12 ${paymentStatus === 'pagado' ? 'bg-green-600 hover:bg-green-700' : ''}`}
                        onClick={() => setPaymentStatus('pagado')}
                        data-testid="payment-status-pagado"
                      >
                        <CreditCard className="h-4 w-4 mr-2" />
                        Pagado
                      </Button>
                      <Button
                        type="button"
                        variant={paymentStatus === 'por_cobrar' ? 'default' : 'outline'}
                        className={`w-full h-12 ${paymentStatus === 'por_cobrar' ? 'bg-orange-600 hover:bg-orange-700' : ''}`}
                        onClick={() => setPaymentStatus('por_cobrar')}
                        data-testid="payment-status-por-cobrar"
                      >
                        <Wallet className="h-4 w-4 mr-2" />
                        Por Cobrar
                      </Button>
                    </div>
                  </div>

                  {paymentStatus === 'pagado' && (
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2">
                        <CreditCard className="h-4 w-4" />
                        Forma de Pago *
                      </Label>
                      <Select
                        value={selectedPaymentMethod}
                        onValueChange={setSelectedPaymentMethod}
                      >
                        <SelectTrigger className="h-12" data-testid="select-payment-method">
                          <SelectValue placeholder="Seleccione forma de pago" />
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
                  )}

                  {paymentStatus === 'por_cobrar' && (
                    <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg space-y-3">
                      <p className="text-sm text-orange-400">
                        <Wallet className="h-4 w-4 inline mr-2" />
                        La factura se registrará como crédito y aparecerá en el módulo de Fios.
                      </p>
                      <div className="space-y-1">
                        <Label htmlFor="pos-due-date" className="flex items-center gap-2 text-sm">
                          <CalendarClock className="h-4 w-4" /> Fecha de vencimiento
                        </Label>
                        <Input id="pos-due-date" type="date" min={ymd(new Date())} value={dueDate}
                               onChange={(e) => setDueDate(e.target.value)} className="max-w-[12rem]" data-testid="pos-due-date-input" />
                        <p className="text-xs text-muted-foreground">
                          {creditStatus
                            ? `Plazo ${creditStatus.term_days === creditStatus.default_term_days ? 'por defecto' : 'del cliente'}: ${creditStatus.term_days} día(s)`
                              + (dueDate ? ` · vence el ${dmy(dueDate)}` : '')
                            : 'Vacío: se usa el plazo del cliente o el de Config. Sistema.'}
                        </p>
                      </div>
                      {creditStatus && creditStatus.credit_limit && totals.total > (creditStatus.available || 0) + 0.005 && (
                        <p className="text-sm text-red-400" data-testid="pos-credit-limit-warning">
                          <AlertTriangle className="h-4 w-4 inline mr-2" />
                          Esta venta ({money0(totals.total)}) supera el cupo disponible del cliente ({money0(Math.max(0, creditStatus.available))}).
                          No se puede fiar: cóbrala de contado o pide a un administrador que amplíe el cupo.
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Totals Summary */}
                <div className="bg-muted/30 rounded-lg p-6 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Subtotal:</span>
                    <span className="font-mono" data-testid="cart-subtotal">
                      ${totals.subtotal.toLocaleString('es-CO', {minimumFractionDigits: 2})}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">IVA Total:</span>
                    <span className="font-mono" data-testid="cart-tax">
                      ${totals.totalTax.toLocaleString('es-CO', {minimumFractionDigits: 2})}
                    </span>
                  </div>
                  <div className="border-t pt-3">
                    <div className="flex justify-between text-2xl font-bold">
                      <span>TOTAL:</span>
                      <span className="font-mono text-primary" data-testid="cart-total">
                        ${totals.total.toLocaleString('es-CO', {minimumFractionDigits: 2})}
                      </span>
                    </div>
                  </div>

                  <Button
                    className="w-full h-14 text-lg mt-4 font-semibold shadow-md"
                    size="lg"
                    onClick={handleCheckout}
                    disabled={isProcessing || cart.length === 0 || !selectedClient || (paymentStatus === 'pagado' && !selectedPaymentMethod) || !canCreate('pos') || (cashState.required && !cashState.open)
                      || (paymentStatus === 'por_cobrar' && creditStatus && creditStatus.credit_limit && totals.total > (creditStatus.available || 0) + 0.005)}
                    data-testid="checkout-button"
                    title={!canCreate('pos') ? 'Tu rol no tiene permiso para registrar ventas' : undefined}
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                        Procesando venta...
                      </>
                    ) : paymentStatus === 'pagado' ? (
                      <>
                        <CreditCard className="h-5 w-5 mr-2" />
                        Procesar Venta (Pagado)
                      </>
                    ) : (
                      <>
                        <Wallet className="h-5 w-5 mr-2" />
                        Procesar Venta (Crédito)
                      </>
                    )}
                  </Button>
                  {!canCreate('pos') && (
                    <p className="text-xs text-center text-muted-foreground mt-2" data-testid="pos-no-permission">
                      Tu rol no tiene permiso para registrar ventas. Pídeselo a un administrador.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default POS;
