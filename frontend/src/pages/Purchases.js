import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Plus, Trash2, Search, Package, Truck } from 'lucide-react';
import { toast } from 'sonner';

const Purchases = () => {
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  
  // Supplier autocomplete state
  const [supplierSearch, setSupplierSearch] = useState('');
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [showSupplierDropdown, setShowSupplierDropdown] = useState(false);
  const supplierInputRef = useRef(null);
  
  // Items state
  const [items, setItems] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (supplierInputRef.current && !supplierInputRef.current.contains(event.target)) {
        setShowSupplierDropdown(false);
      }
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

  // Filter suppliers based on search
  const filteredSuppliers = suppliers.filter(s =>
    supplierSearch === '' ||
    s.name.toLowerCase().includes(supplierSearch.toLowerCase()) ||
    (s.nit && s.nit.toLowerCase().includes(supplierSearch.toLowerCase()))
  );

  const handleSelectSupplier = (supplier) => {
    setSelectedSupplier(supplier);
    setSupplierSearch(supplier.name);
    setShowSupplierDropdown(false);
  };

  const handleAddItem = () => {
    setItems([...items, { 
      barcode: '', 
      product_name: '', 
      quantity: 1, 
      unit_cost: 0, 
      total: 0,
      productSearch: '',
      showProductDropdown: false,
      selectedProduct: null
    }]);
  };

  const handleRemoveItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  // Filter products for a specific item
  const getFilteredProducts = (searchTerm) => {
    if (!searchTerm) return products.slice(0, 10);
    return products.filter(p =>
      p.barcode.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.name.toLowerCase().includes(searchTerm.toLowerCase())
    ).slice(0, 10);
  };

  const handleProductSearch = (index, value) => {
    const newItems = [...items];
    newItems[index].productSearch = value;
    newItems[index].showProductDropdown = true;
    
    // If user clears the input, reset the product selection
    if (!value) {
      newItems[index].selectedProduct = null;
      newItems[index].barcode = '';
      newItems[index].product_name = '';
      newItems[index].unit_cost = 0;
      newItems[index].total = 0;
    }
    
    setItems(newItems);
  };

  const handleSelectProduct = (index, product) => {
    const newItems = [...items];
    newItems[index].selectedProduct = product;
    newItems[index].productSearch = `${product.barcode} - ${product.name}`;
    newItems[index].barcode = product.barcode;
    newItems[index].product_name = product.name;
    newItems[index].unit_cost = product.purchase_price;
    newItems[index].showProductDropdown = false;
    
    // Calculate total
    newItems[index].total = parseFloat(newItems[index].quantity) * parseFloat(product.purchase_price);
    
    setItems(newItems);
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    
    // Recalculate total when quantity or unit_cost changes
    if (field === 'quantity' || field === 'unit_cost') {
      const qty = parseFloat(newItems[index].quantity) || 0;
      const cost = parseFloat(newItems[index].unit_cost) || 0;
      newItems[index].total = qty * cost;
    }
    
    setItems(newItems);
  };

  const handleProductDropdownToggle = (index, show) => {
    const newItems = [...items];
    newItems[index].showProductDropdown = show;
    setItems(newItems);
  };

  const calculateTotal = () => {
    return items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSupplier) {
      toast.error('Selecciona un proveedor');
      return;
    }
    if (items.length === 0) {
      toast.error('Agrega al menos un producto');
      return;
    }
    
    // Validate all items have a product selected
    const invalidItems = items.filter(item => !item.barcode || !item.product_name);
    if (invalidItems.length > 0) {
      toast.error('Todos los items deben tener un producto seleccionado');
      return;
    }

    try {
      await axios.post(`${API}/purchases`, {
        supplier_name: selectedSupplier.name,
        items: items.map(item => ({
          barcode: item.barcode,
          product_name: item.product_name,
          quantity: parseInt(item.quantity),
          unit_cost: parseFloat(item.unit_cost),
          total: parseFloat(item.total)
        }))
      });
      toast.success('Compra registrada exitosamente');
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al registrar compra');
    }
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setSelectedSupplier(null);
    setSupplierSearch('');
    setItems([]);
  };

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="purchases-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Compras</h1>
          <p className="text-muted-foreground mt-2">Registro de compras a proveedores</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => setDialogOpen(true)} data-testid="create-purchase-button">
              <Plus className="h-4 w-4 mr-2" />
              Nueva Compra
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="purchase-dialog">
            <DialogHeader>
              <DialogTitle>Nueva Compra</DialogTitle>
              <DialogDescription>Registra una compra a proveedor</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                {/* Supplier Autocomplete */}
                <div className="space-y-2" ref={supplierInputRef}>
                  <Label htmlFor="supplier" className="flex items-center gap-2">
                    <Truck className="h-4 w-4" />
                    Proveedor *
                  </Label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Buscar proveedor por nombre o NIT..."
                      value={supplierSearch}
                      onChange={(e) => {
                        setSupplierSearch(e.target.value);
                        setShowSupplierDropdown(true);
                        if (!e.target.value) setSelectedSupplier(null);
                      }}
                      onFocus={() => setShowSupplierDropdown(true)}
                      className="pl-10"
                      data-testid="supplier-search-input"
                    />
                    {showSupplierDropdown && filteredSuppliers.length > 0 && (
                      <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {filteredSuppliers.map((supplier) => (
                          <div
                            key={supplier.name}
                            className={`px-4 py-2 cursor-pointer hover:bg-accent transition-colors ${
                              selectedSupplier?.name === supplier.name ? 'bg-accent' : ''
                            }`}
                            onClick={() => handleSelectSupplier(supplier)}
                            data-testid={`supplier-option-${supplier.name}`}
                          >
                            <div className="font-medium">{supplier.name}</div>
                            {supplier.nit && (
                              <div className="text-xs text-muted-foreground">NIT: {supplier.nit}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {showSupplierDropdown && supplierSearch && filteredSuppliers.length === 0 && (
                      <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg p-4 text-center text-muted-foreground">
                        No se encontraron proveedores
                      </div>
                    )}
                  </div>
                  {selectedSupplier && (
                    <div className="text-xs text-green-500 flex items-center gap-1">
                      ✓ Proveedor seleccionado: {selectedSupplier.name}
                    </div>
                  )}
                </div>

                {/* Items Section */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Items de Compra</Label>
                    <Button 
                      type="button" 
                      variant="outline" 
                      size="sm" 
                      onClick={handleAddItem} 
                      data-testid="add-purchase-item-button"
                    >
                      <Plus className="h-3 w-3 mr-1" />
                      Agregar Item
                    </Button>
                  </div>
                  
                  {items.length === 0 && (
                    <div className="text-center py-8 border border-dashed border-border rounded-lg text-muted-foreground">
                      <Package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p>No hay items agregados</p>
                      <p className="text-xs">Haz clic en "Agregar Item" para comenzar</p>
                    </div>
                  )}
                  
                  {items.map((item, index) => (
                    <Card key={index} className="border-l-4 border-l-primary">
                      <CardContent className="p-4">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          {/* Product Autocomplete */}
                          <div className="space-y-2 md:col-span-2 relative">
                            <Label className="flex items-center gap-2">
                              <Package className="h-4 w-4" />
                              Producto *
                            </Label>
                            <div className="relative">
                              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                              <Input
                                placeholder="Buscar por nombre o código..."
                                value={item.productSearch}
                                onChange={(e) => handleProductSearch(index, e.target.value)}
                                onFocus={() => handleProductDropdownToggle(index, true)}
                                className="pl-10"
                                data-testid={`product-search-input-${index}`}
                              />
                              {item.showProductDropdown && (
                                <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                                  {getFilteredProducts(item.productSearch).length > 0 ? (
                                    getFilteredProducts(item.productSearch).map((product) => (
                                      <div
                                        key={product.barcode}
                                        className={`px-4 py-2 cursor-pointer hover:bg-accent transition-colors ${
                                          item.barcode === product.barcode ? 'bg-accent' : ''
                                        }`}
                                        onClick={() => handleSelectProduct(index, product)}
                                        data-testid={`product-option-${product.barcode}`}
                                      >
                                        <div className="flex justify-between items-center">
                                          <div>
                                            <div className="font-medium">{product.name}</div>
                                            <div className="text-xs text-muted-foreground font-mono">
                                              {product.barcode}
                                            </div>
                                          </div>
                                          <div className="text-right">
                                            <div className="text-sm font-mono">${product.purchase_price?.toLocaleString()}</div>
                                            <div className="text-xs text-muted-foreground">Stock: {product.stock}</div>
                                          </div>
                                        </div>
                                      </div>
                                    ))
                                  ) : (
                                    <div className="p-4 text-center text-muted-foreground">
                                      No se encontraron productos
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            {item.selectedProduct && (
                              <div className="text-xs text-green-500">
                                ✓ {item.product_name}
                              </div>
                            )}
                          </div>
                          
                          {/* Quantity */}
                          <div className="space-y-2">
                            <Label>Cantidad</Label>
                            <Input
                              type="number"
                              min="1"
                              value={item.quantity}
                              onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                              data-testid={`item-quantity-${index}`}
                            />
                          </div>
                          
                          {/* Unit Cost */}
                          <div className="space-y-2">
                            <Label>Costo Unitario</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min="0"
                              value={item.unit_cost}
                              onChange={(e) => handleItemChange(index, 'unit_cost', e.target.value)}
                              data-testid={`item-unit-cost-${index}`}
                            />
                          </div>
                        </div>
                        
                        {/* Total and Remove */}
                        <div className="flex justify-between items-center mt-4 pt-4 border-t border-border">
                          <div className="text-sm">
                            <span className="text-muted-foreground">Total Item: </span>
                            <span className="font-bold font-mono text-lg">
                              ${(parseFloat(item.total) || 0).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => handleRemoveItem(index)}
                            data-testid={`remove-item-${index}`}
                          >
                            <Trash2 className="h-4 w-4 mr-1" />
                            Eliminar
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* Total */}
                {items.length > 0 && (
                  <div className="border-t pt-4">
                    <div className="flex justify-between text-xl font-bold">
                      <span>Total Compra:</span>
                      <span className="font-mono text-primary" data-testid="purchase-total">
                        ${calculateTotal().toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" data-testid="save-purchase-button">
                  Registrar Compra
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead className="text-right font-mono">Total</TableHead>
              <TableHead>Registrado por</TableHead>
              <TableHead>Fecha</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {purchases.map((purchase, index) => (
              <TableRow key={index} data-testid={`purchase-row-${index}`}>
                <TableCell className="font-semibold">{purchase.supplier_name}</TableCell>
                <TableCell className="text-right font-mono font-bold">
                  ${purchase.total?.toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{purchase.created_by}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(purchase.created_at).toLocaleString('es-CO')}
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
