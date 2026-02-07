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
import { Search, Minus, Plus, Trash2, ShoppingCart, CreditCard, Wallet, User, AlertCircle, Package } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const POS = () => {
  const { canCreate } = usePermissions();
  const [products, setProducts] = useState([]);
  const [clients, setClients] = useState([]);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [searchProduct, setSearchProduct] = useState('');
  const [searchClient, setSearchClient] = useState('');
  const [selectedClient, setSelectedClient] = useState(null);
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Payment fields
  const [paymentStatus, setPaymentStatus] = useState('pagado');
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
      
      if (paymentMethodsRes.data.length > 0) {
        setSelectedPaymentMethod(paymentMethodsRes.data[0].name);
      }
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const getProductPrice = (product) => {
    let unitPrice = product.purchase_price * 1.3;
    if (selectedClient && product.prices && product.prices.length > 0) {
      const clientPriceList = product.prices.find(p => p.price_list_name === selectedClient.price_list);
      if (clientPriceList) {
        unitPrice = clientPriceList.price;
      }
    }
    return unitPrice;
  };

  const addToCart = (product) => {
    if (!selectedClient) {
      toast.error('Primero selecciona un cliente');
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
      
      if (paymentStatus === 'pagado') {
        setTimeout(() => downloadTicket(response.data.invoice_number), 500);
      }
      
      setCart([]);
      setSelectedClient(null);
      setSearchClient('');
      setSearchProduct('');
      setPaymentStatus('pagado');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al crear factura');
    }
  };

  const handleClientChange = (client) => {
    if (cart.length > 0 && selectedClient && selectedClient.document_number !== client.document_number) {
      const updatedCart = cart.map(item => {
        const product = products.find(p => p.barcode === item.barcode);
        if (product) {
          let unitPrice = product.purchase_price * 1.3;
          if (client && product.prices && product.prices.length > 0) {
            const clientPriceList = product.prices.find(p => p.price_list_name === client.price_list);
            if (clientPriceList) {
              unitPrice = clientPriceList.price;
            }
          }
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

  // Only show products when user is searching
  const filteredProducts = searchProduct.length >= 2
    ? products.filter(p =>
        p.barcode.toLowerCase().includes(searchProduct.toLowerCase()) ||
        p.name.toLowerCase().includes(searchProduct.toLowerCase())
      ).slice(0, 10)
    : [];

  // Only show clients when user is searching (min 2 characters)
  const filteredClients = searchClient.length >= 2
    ? clients.filter(c =>
        c.document_number.toLowerCase().includes(searchClient.toLowerCase()) ||
        c.first_name.toLowerCase().includes(searchClient.toLowerCase()) ||
        c.last_name.toLowerCase().includes(searchClient.toLowerCase())
      ).slice(0, 10)
    : [];

  const totals = calculateTotals();

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="pos-page" className="space-y-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Punto de Venta (POS)</h1>
        <p className="text-muted-foreground mt-2">Sistema de facturación rápida</p>
      </div>

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
                      <p>No se encontraron clientes para "{searchClient}"</p>
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
                          <p className="font-bold text-lg font-mono text-primary">
                            ${price.toLocaleString()}
                          </p>
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
                  <p>No se encontraron productos para "{searchProduct}"</p>
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
                            <span className="w-12 text-center font-mono font-bold">{item.quantity}</span>
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
                    <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                      <p className="text-sm text-orange-400">
                        <Wallet className="h-4 w-4 inline mr-2" />
                        La factura se registrará como crédito y aparecerá en el módulo de Fios.
                      </p>
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
                    className="w-full h-14 text-lg mt-4"
                    size="lg"
                    onClick={handleCheckout}
                    disabled={cart.length === 0 || !selectedClient || (paymentStatus === 'pagado' && !selectedPaymentMethod) || !canCreate('pos')}
                    data-testid="checkout-button"
                  >
                    {paymentStatus === 'pagado' ? (
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
