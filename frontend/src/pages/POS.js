import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
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
import { Search, Minus, Plus, Trash2, ShoppingCart, CreditCard, Wallet, Download } from 'lucide-react';
import { toast } from 'sonner';

const POS = () => {
  const [products, setProducts] = useState([]);
  const [clients, setClients] = useState([]);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [searchProduct, setSearchProduct] = useState('');
  const [searchClient, setSearchClient] = useState('');
  const [selectedClient, setSelectedClient] = useState(null);
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // New fields for payment
  const [paymentStatus, setPaymentStatus] = useState('pagado'); // 'pagado' or 'por_cobrar'
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [productsRes, clientsRes, paymentMethodsRes] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/clients`),
        axios.get(`${API}/payment-methods/active`)
      ]);
      setProducts(productsRes.data);
      setClients(clientsRes.data);
      setPaymentMethods(paymentMethodsRes.data);
      
      // Set default payment method if available
      if (paymentMethodsRes.data.length > 0) {
        setSelectedPaymentMethod(paymentMethodsRes.data[0].name);
      }
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const addToCart = (product) => {
    if (product.stock <= 0) {
      toast.error('Producto sin stock');
      return;
    }

    const existingItem = cart.find(item => item.barcode === product.barcode);
    if (existingItem) {
      if (existingItem.quantity >= product.stock) {
        toast.error('Stock insuficiente');
        return;
      }
      setCart(cart.map(item =>
        item.barcode === product.barcode
          ? { ...item, quantity: item.quantity + 1 }
          : item
      ));
    } else {
      // Get price based on client's price list
      let unitPrice = product.purchase_price * 1.3; // Default markup
      if (selectedClient && product.prices.length > 0) {
        const clientPriceList = product.prices.find(p => p.price_list_name === selectedClient.price_list);
        if (clientPriceList) {
          unitPrice = clientPriceList.price;
        }
      }

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
      const response = await axios.get(`${API}/pos/invoices/${invoiceNumber}/ticket`, {
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
    if (!selectedClient) {
      toast.error('Selecciona un cliente');
      return;
    }
    if (cart.length === 0) {
      toast.error('El carrito está vacío');
      return;
    }
    
    // Validate payment method if status is 'pagado'
    if (paymentStatus === 'pagado' && !selectedPaymentMethod) {
      toast.error('Selecciona una forma de pago');
      return;
    }

    try {
      const invoiceData = {
        client_document: selectedClient.document_number,
        items: cart,
        payment_status: paymentStatus,
        payment_method: paymentStatus === 'pagado' ? selectedPaymentMethod : null
      };
      
      const response = await axios.post(`${API}/invoices`, invoiceData);
      
      const statusMessage = paymentStatus === 'pagado' 
        ? `Factura ${response.data.invoice_number} creada - PAGADA con ${selectedPaymentMethod}`
        : `Factura ${response.data.invoice_number} creada - POR COBRAR`;
      
      toast.success(statusMessage, {
        action: paymentStatus === 'pagado' ? {
          label: 'Descargar Ticket',
          onClick: () => downloadTicket(response.data.invoice_number)
        } : undefined,
        duration: 5000
      });
      
      // Auto-download ticket for paid invoices
      if (paymentStatus === 'pagado') {
        setTimeout(() => downloadTicket(response.data.invoice_number), 500);
      }
      
      // Reset form
      setCart([]);
      setSelectedClient(null);
      setPaymentStatus('pagado');
      fetchData(); // Refresh products to update stock
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al crear factura');
    }
  };

  const filteredProducts = products.filter(p =>
    searchProduct === '' ||
    p.barcode.toLowerCase().includes(searchProduct.toLowerCase()) ||
    p.name.toLowerCase().includes(searchProduct.toLowerCase())
  ).slice(0, 20);

  const filteredClients = clients.filter(c =>
    searchClient === '' ||
    c.document_number.toLowerCase().includes(searchClient.toLowerCase()) ||
    c.first_name.toLowerCase().includes(searchClient.toLowerCase()) ||
    c.last_name.toLowerCase().includes(searchClient.toLowerCase())
  ).slice(0, 10);

  const totals = calculateTotals();

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="pos-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Punto de Venta (POS)</h1>
        <p className="text-muted-foreground mt-2">Sistema de facturación rápida</p>
      </div>

      <div className="pos-split">
        {/* Left: Products */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Productos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Buscar producto..."
                  value={searchProduct}
                  onChange={(e) => setSearchProduct(e.target.value)}
                  className="pl-10"
                  data-testid="pos-search-product-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-2 max-h-[60vh] overflow-y-auto">
                {filteredProducts.map((product, index) => (
                  <Card
                    key={product.barcode}
                    className="cursor-pointer card-hover"
                    onClick={() => addToCart(product)}
                    data-testid={`pos-product-${index}`}
                  >
                    <CardContent className="p-4">
                      <p className="font-semibold text-sm truncate">{product.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">{product.barcode}</p>
                      <p className="text-sm font-mono mt-2">Stock: {product.stock}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Cart & Checkout */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Cliente</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Buscar cliente..."
                  value={searchClient}
                  onChange={(e) => setSearchClient(e.target.value)}
                  className="pl-10"
                  data-testid="pos-search-client-input"
                />
              </div>

              {selectedClient ? (
                <div className="p-3 bg-secondary rounded-md" data-testid="selected-client">
                  <p className="font-semibold">{`${selectedClient.first_name} ${selectedClient.last_name}`}</p>
                  <p className="text-xs text-muted-foreground font-mono">{selectedClient.document_number}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => setSelectedClient(null)}
                  >
                    Cambiar
                  </Button>
                </div>
              ) : (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {filteredClients.map((client, index) => (
                    <div
                      key={client.document_number}
                      className="p-2 border rounded-md cursor-pointer hover:bg-accent"
                      onClick={() => setSelectedClient(client)}
                      data-testid={`pos-client-${index}`}
                    >
                      <p className="text-sm font-medium">{`${client.first_name} ${client.last_name}`}</p>
                      <p className="text-xs text-muted-foreground font-mono">{client.document_number}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <ShoppingCart className="h-5 w-5" />
                Carrito ({cart.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {cart.map((item, index) => (
                  <div key={item.barcode} className="flex justify-between items-center p-2 border rounded-md" data-testid={`cart-item-${index}`}>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.product_name}</p>
                      <p className="text-xs text-muted-foreground font-mono">${item.unit_price.toFixed(2)} c/u</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => updateQuantity(item.barcode, -1)}
                        data-testid={`decrease-quantity-${index}`}
                      >
                        <Minus className="h-3 w-3" />
                      </Button>
                      <span className="w-8 text-center font-mono text-sm">{item.quantity}</span>
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => updateQuantity(item.barcode, 1)}
                        data-testid={`increase-quantity-${index}`}
                      >
                        <Plus className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => removeFromCart(item.barcode)}
                        data-testid={`remove-item-${index}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              {cart.length === 0 && (
                <p className="text-center text-muted-foreground py-8" data-testid="empty-cart">Carrito vacío</p>
              )}

              <div className="border-t pt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Subtotal:</span>
                  <span className="font-mono" data-testid="cart-subtotal">${totals.subtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>IVA:</span>
                  <span className="font-mono" data-testid="cart-tax">${totals.totalTax.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-lg font-bold">
                  <span>Total:</span>
                  <span className="font-mono" data-testid="cart-total">${totals.total.toFixed(2)}</span>
                </div>
              </div>

              {/* Payment Section */}
              <div className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Wallet className="h-4 w-4" />
                    Estado de Pago
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant={paymentStatus === 'pagado' ? 'default' : 'outline'}
                      className={`w-full ${paymentStatus === 'pagado' ? 'bg-green-600 hover:bg-green-700' : ''}`}
                      onClick={() => setPaymentStatus('pagado')}
                      data-testid="payment-status-pagado"
                    >
                      <CreditCard className="h-4 w-4 mr-2" />
                      Pagado
                    </Button>
                    <Button
                      type="button"
                      variant={paymentStatus === 'por_cobrar' ? 'default' : 'outline'}
                      className={`w-full ${paymentStatus === 'por_cobrar' ? 'bg-orange-600 hover:bg-orange-700' : ''}`}
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
                    <Label htmlFor="payment-method" className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4" />
                      Forma de Pago *
                    </Label>
                    <Select
                      value={selectedPaymentMethod}
                      onValueChange={setSelectedPaymentMethod}
                    >
                      <SelectTrigger data-testid="select-payment-method">
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
                  <div className="p-3 bg-orange-500/10 border border-orange-500/30 rounded-md">
                    <p className="text-sm text-orange-400">
                      <Wallet className="h-4 w-4 inline mr-2" />
                      La factura se registrará como crédito (fiado) y aparecerá en el módulo de Fios para gestionar los abonos.
                    </p>
                  </div>
                )}
              </div>

              <Button
                className="w-full"
                size="lg"
                onClick={handleCheckout}
                disabled={cart.length === 0 || !selectedClient || (paymentStatus === 'pagado' && !selectedPaymentMethod)}
                data-testid="checkout-button"
              >
                {paymentStatus === 'pagado' ? (
                  <>
                    <CreditCard className="h-4 w-4 mr-2" />
                    Procesar Venta (Pagado)
                  </>
                ) : (
                  <>
                    <Wallet className="h-4 w-4 mr-2" />
                    Procesar Venta (Crédito)
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default POS;
