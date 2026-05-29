import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Trash2, Search, Package, Truck, ShoppingBag, Edit, Eye, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const Purchases = () => {
  const { canCreate, canUpdate } = usePermissions();
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('create'); // create | edit | readonly
  const [currentPurchase, setCurrentPurchase] = useState(null);

  // Form state
  const [supplierSearch, setSupplierSearch] = useState('');
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [showSupplierDropdown, setShowSupplierDropdown] = useState(false);
  const supplierInputRef = useRef(null);

  const [productSearch, setProductSearch] = useState('');
  const [showProductDropdown, setShowProductDropdown] = useState(false);
  const productInputRef = useRef(null);

  const [items, setItems] = useState([]);

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (supplierInputRef.current && !supplierInputRef.current.contains(event.target)) setShowSupplierDropdown(false);
      if (productInputRef.current && !productInputRef.current.contains(event.target)) setShowProductDropdown(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchData = async () => {
    try {
      const [purchasesRes, suppliersRes, productsRes] = await Promise.all([
        axios.get(`${API}/purchases`),
        axios.get(`${API}/suppliers`),
        axios.get(`${API}/products`)
      ]);
      setPurchases(purchasesRes.data);
      setSuppliers(suppliersRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const filteredSuppliers = supplierSearch.length >= 2
    ? suppliers.filter(s => s.name.toLowerCase().includes(supplierSearch.toLowerCase()))
    : [];

  const filteredProducts = productSearch.length >= 2
    ? products.filter(p =>
        p.barcode.toLowerCase().includes(productSearch.toLowerCase()) ||
        p.name.toLowerCase().includes(productSearch.toLowerCase())
      ).slice(0, 8)
    : [];

  const handleSelectSupplier = (supplier) => {
    setSelectedSupplier(supplier);
    setSupplierSearch(supplier.name);
    setShowSupplierDropdown(false);
  };

  const addProductToItems = (product) => {
    const existing = items.find(i => i.barcode === product.barcode);
    if (existing) {
      setItems(items.map(i =>
        i.barcode === product.barcode
          ? { ...i, quantity: i.quantity + 1, total: (i.quantity + 1) * i.unit_cost }
          : i
      ));
    } else {
      setItems([...items, {
        barcode: product.barcode,
        product_name: product.name,
        quantity: 1,
        unit_cost: product.purchase_price || 0,
        total: product.purchase_price || 0
      }]);
    }
    setProductSearch('');
    setShowProductDropdown(false);
  };

  const updateItemField = (barcode, field, value) => {
    setItems(items.map(item => {
      if (item.barcode !== barcode) return item;
      const updated = { ...item, [field]: value };
      const qty = parseFloat(field === 'quantity' ? value : item.quantity) || 0;
      const cost = parseFloat(field === 'unit_cost' ? value : item.unit_cost) || 0;
      updated.total = qty * cost;
      return updated;
    }));
  };

  const setItemQuantity = (barcode, value) => {
    const qty = parseInt(value) || 0;
    if (qty <= 0) return;
    updateItemField(barcode, 'quantity', qty);
  };

  const removeItem = (barcode) => {
    setItems(items.filter(i => i.barcode !== barcode));
  };

  const calculateTotal = () => items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);

  // === Dialog open helpers ===
  const openCreateDialog = () => {
    setDialogMode('create');
    setCurrentPurchase(null);
    setSelectedSupplier(null);
    setSupplierSearch('');
    setProductSearch('');
    setItems([]);
    setDialogOpen(true);
  };

  const openEditDialog = (purchase) => {
    setDialogMode('edit');
    setCurrentPurchase(purchase);
    const sup = suppliers.find(s => s.name === purchase.supplier_name);
    setSelectedSupplier(sup || { name: purchase.supplier_name });
    setSupplierSearch(purchase.supplier_name);
    setItems(purchase.items.map(i => ({ ...i })));
    setProductSearch('');
    setDialogOpen(true);
  };

  const openViewDialog = (purchase) => {
    setDialogMode('readonly');
    setCurrentPurchase(purchase);
    const sup = suppliers.find(s => s.name === purchase.supplier_name);
    setSelectedSupplier(sup || { name: purchase.supplier_name });
    setSupplierSearch(purchase.supplier_name);
    setItems(purchase.items.map(i => ({ ...i })));
    setProductSearch('');
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setCurrentPurchase(null);
  };

  // === Submit (create / edit) ===
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSupplier) { toast.error('Selecciona un proveedor'); return; }
    if (items.length === 0) { toast.error('Agrega al menos un producto'); return; }

    const payload = {
      supplier_name: selectedSupplier.name,
      items: items.map(item => ({
        barcode: item.barcode,
        product_name: item.product_name,
        quantity: parseInt(item.quantity),
        unit_cost: parseFloat(item.unit_cost),
        total: parseFloat(item.total)
      }))
    };

    try {
      if (dialogMode === 'edit') {
        await axios.put(`${API}/purchases/${currentPurchase.purchase_number}`, payload);
        toast.success('Compra actualizada');
      } else {
        await axios.post(`${API}/purchases`, payload);
        toast.success('Compra creada en estado Borrador');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar compra');
    }
  };

  // === Confirm purchase ===
  const handleConfirm = async (purchaseNumber) => {
    if (!window.confirm('¿Estás seguro de procesar esta compra?\nEsto actualizará el inventario y no se podrá editar.')) return;
    try {
      await axios.post(`${API}/purchases/${purchaseNumber}/confirm`);
      toast.success('Compra confirmada e inventario actualizado');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al confirmar compra');
    }
  };

  const isReadonly = dialogMode === 'readonly';
  const dialogTitle = dialogMode === 'create' ? 'Nueva Compra' : dialogMode === 'edit' ? 'Editar Compra' : 'Detalle de Compra';
  const dialogDesc = dialogMode === 'create' ? 'Se guardará como borrador' : dialogMode === 'edit' ? `Editando ${currentPurchase?.purchase_number}` : `${currentPurchase?.purchase_number} — Confirmada`;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="purchases-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Compras</h1>
          <p className="text-muted-foreground mt-2">Registro de compras a proveedores</p>
        </div>
        {canCreate('purchases') && (
          <Button onClick={openCreateDialog} data-testid="create-purchase-button">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Compra
          </Button>
        )}
      </div>

      {/* ======= DIALOG ======= */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="purchase-dialog">
          <DialogHeader>
            <DialogTitle>{dialogTitle}</DialogTitle>
            <DialogDescription>{dialogDesc}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-5 py-4">

              {/* 1. Supplier */}
              <div className="p-4 border rounded-lg space-y-2" ref={supplierInputRef}>
                <Label className="flex items-center gap-2 font-semibold">
                  <Truck className="h-4 w-4" />
                  1. Proveedor
                </Label>
                {selectedSupplier ? (
                  <div className="flex items-center justify-between p-3 bg-accent/30 rounded-md">
                    <div>
                      <p className="font-medium">{selectedSupplier.name}</p>
                      <p className="text-xs text-muted-foreground">{selectedSupplier.contact_name || ''}</p>
                    </div>
                    {!isReadonly && (
                      <Button type="button" variant="outline" size="sm" onClick={() => { setSelectedSupplier(null); setSupplierSearch(''); }}>
                        Cambiar
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Buscar proveedor... (mínimo 2 caracteres)"
                      value={supplierSearch}
                      onChange={(e) => { setSupplierSearch(e.target.value); setShowSupplierDropdown(true); }}
                      onFocus={() => setShowSupplierDropdown(true)}
                      className="pl-10"
                      disabled={isReadonly}
                      data-testid="supplier-search-input"
                    />
                    {showSupplierDropdown && supplierSearch.length >= 2 && (
                      <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                        {filteredSuppliers.length > 0 ? filteredSuppliers.map((supplier) => (
                          <div
                            key={supplier.name}
                            className="px-4 py-2 cursor-pointer hover:bg-accent transition-colors"
                            onClick={() => handleSelectSupplier(supplier)}
                          >
                            <div className="font-medium">{supplier.name}</div>
                            {supplier.contact_name && <div className="text-xs text-muted-foreground">{supplier.contact_name}</div>}
                          </div>
                        )) : (
                          <div className="p-3 text-center text-muted-foreground text-sm">No se encontraron proveedores</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 2. Product Search */}
              {!isReadonly && (
                <div className="p-4 border rounded-lg space-y-2" ref={productInputRef}>
                  <Label className="flex items-center gap-2 font-semibold">
                    <Package className="h-4 w-4" />
                    2. Agregar Productos
                  </Label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Buscar producto por nombre o código..."
                      value={productSearch}
                      onChange={(e) => { setProductSearch(e.target.value); setShowProductDropdown(true); }}
                      onFocus={() => { if (productSearch.length >= 2) setShowProductDropdown(true); }}
                      className="pl-10"
                      data-testid="product-search-input"
                    />
                    {showProductDropdown && productSearch.length >= 2 && (
                      <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                        {filteredProducts.length > 0 ? filteredProducts.map((product) => {
                          const inItems = items.find(i => i.barcode === product.barcode);
                          return (
                            <div
                              key={product.barcode}
                              className="px-4 py-2 cursor-pointer hover:bg-accent transition-colors flex justify-between items-center"
                              onClick={() => addProductToItems(product)}
                            >
                              <div>
                                <div className="font-medium">{product.name}</div>
                                <div className="text-xs text-muted-foreground font-mono">{product.barcode}</div>
                              </div>
                              <div className="text-right flex items-center gap-3">
                                <div>
                                  <div className="text-sm font-mono">${product.purchase_price?.toLocaleString()}</div>
                                  <div className="text-xs text-muted-foreground">Stock: {product.stock}</div>
                                </div>
                                {inItems && <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded">x{inItems.quantity}</span>}
                                <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); addProductToItems(product); }}>
                                  <Plus className="h-3 w-3 mr-1" />Agregar
                                </Button>
                              </div>
                            </div>
                          );
                        }) : (
                          <div className="p-3 text-center text-muted-foreground text-sm">No se encontraron productos</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 3. Items Table */}
              <div className="p-4 border rounded-lg space-y-3">
                <Label className="flex items-center gap-2 font-semibold">
                  <ShoppingBag className="h-4 w-4" />
                  {isReadonly ? '2' : '3'}. Detalle de Compra
                  {items.length > 0 && <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">{items.length} items</span>}
                </Label>

                {items.length === 0 ? (
                  <div className="text-center py-6 text-muted-foreground">
                    <Package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Busca y agrega productos para comenzar</p>
                  </div>
                ) : (
                  <>
                    <div className="border rounded-md overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Producto</TableHead>
                            <TableHead className="w-28 text-center">Cantidad</TableHead>
                            <TableHead className="w-36 text-center">Costo Unit.</TableHead>
                            <TableHead className="w-32 text-right">Total</TableHead>
                            {!isReadonly && <TableHead className="w-12"></TableHead>}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {items.map((item) => (
                            <TableRow key={item.barcode}>
                              <TableCell>
                                <div className="font-medium">{item.product_name}</div>
                                <div className="text-xs text-muted-foreground font-mono">{item.barcode}</div>
                              </TableCell>
                              <TableCell>
                                {isReadonly ? (
                                  <div className="text-center font-mono font-bold">{item.quantity}</div>
                                ) : (
                                  <input
                                    type="number"
                                    min="1"
                                    className="w-20 text-center font-mono font-bold bg-transparent border rounded-md h-8 mx-auto block [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                    value={item.quantity}
                                    onFocus={(e) => e.target.select()}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      if (val === '') {
                                        setItems(items.map(i => i.barcode === item.barcode ? { ...i, quantity: '' } : i));
                                      } else {
                                        setItemQuantity(item.barcode, val);
                                      }
                                    }}
                                    onBlur={(e) => {
                                      if (!e.target.value || parseInt(e.target.value) <= 0) setItemQuantity(item.barcode, 1);
                                    }}
                                    data-testid={`item-quantity-${item.barcode}`}
                                  />
                                )}
                              </TableCell>
                              <TableCell>
                                {isReadonly ? (
                                  <div className="text-center font-mono">${parseFloat(item.unit_cost).toLocaleString()}</div>
                                ) : (
                                  <div className="flex items-center justify-center gap-1">
                                    <span className="text-muted-foreground">$</span>
                                    <input
                                      type="number"
                                      step="0.01"
                                      min="0"
                                      className="w-28 text-center font-mono bg-transparent border rounded-md h-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                      value={item.unit_cost}
                                      onFocus={(e) => e.target.select()}
                                      onChange={(e) => updateItemField(item.barcode, 'unit_cost', e.target.value)}
                                      onBlur={(e) => { if (!e.target.value) updateItemField(item.barcode, 'unit_cost', 0); }}
                                      data-testid={`item-cost-${item.barcode}`}
                                    />
                                  </div>
                                )}
                              </TableCell>
                              <TableCell className="text-right font-mono font-bold">
                                ${(parseFloat(item.total) || 0).toLocaleString()}
                              </TableCell>
                              {!isReadonly && (
                                <TableCell>
                                  <Button type="button" variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => removeItem(item.barcode)}>
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              )}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    <div className="flex justify-end pt-2 border-t">
                      <div className="text-right">
                        <span className="text-muted-foreground mr-3">Total Compra:</span>
                        <span className="text-2xl font-bold font-mono" data-testid="purchase-total">
                          ${calculateTotal().toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>
                {isReadonly ? 'Cerrar' : 'Cancelar'}
              </Button>
              {!isReadonly && (
                <Button type="submit" disabled={!selectedSupplier || items.length === 0} data-testid="save-purchase-button">
                  {dialogMode === 'edit' ? 'Actualizar Compra' : 'Guardar Borrador'}
                </Button>
              )}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ======= PURCHASES TABLE ======= */}
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead className="text-right font-mono">Total</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Registrado por</TableHead>
              <TableHead>Fecha</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {purchases.map((purchase, index) => (
              <TableRow key={purchase.purchase_number || index} data-testid={`purchase-row-${index}`}>
                <TableCell className="font-mono font-semibold">{purchase.purchase_number}</TableCell>
                <TableCell>{purchase.supplier_name}</TableCell>
                <TableCell className="text-right font-mono font-bold">
                  ${purchase.total?.toLocaleString('es-CO', { minimumFractionDigits: 0 })}
                </TableCell>
                <TableCell>
                  <Badge variant={purchase.status === 'confirmado' ? 'default' : 'secondary'}
                    className={purchase.status === 'confirmado' ? 'bg-green-600 hover:bg-green-700' : 'bg-yellow-600 hover:bg-yellow-700'}>
                    {purchase.status === 'confirmado' ? 'Confirmado' : 'Borrador'}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{purchase.created_by}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(purchase.created_at).toLocaleString('es-CO')}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {purchase.status === 'borrador' ? (
                      <>
                        {canUpdate('purchases') && (
                          <Button variant="ghost" size="icon" onClick={() => openEditDialog(purchase)} title="Editar" data-testid={`edit-purchase-${index}`}>
                            <Edit className="h-4 w-4" />
                          </Button>
                        )}
                        {canUpdate('purchases') && (
                          <Button variant="ghost" size="icon" className="text-green-500 hover:text-green-600" onClick={() => handleConfirm(purchase.purchase_number)} title="Procesar" data-testid={`confirm-purchase-${index}`}>
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                        )}
                      </>
                    ) : (
                      <Button variant="ghost" size="icon" onClick={() => openViewDialog(purchase)} title="Ver Detalle" data-testid={`view-purchase-${index}`}>
                        <Eye className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {purchases.length === 0 && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-purchases">
          No se encontraron compras registradas
        </div>
      )}
    </div>
  );
};

export default Purchases;
