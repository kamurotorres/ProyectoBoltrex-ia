import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Search, Trash2, ShoppingBag } from 'lucide-react';
import { toast } from 'sonner';

const Purchases = () => {
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState('');
  const [items, setItems] = useState([]);
  const [searchProduct, setSearchProduct] = useState('');

  useEffect(() => {
    fetchData();
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

  const handleAddItem = () => {
    setItems([...items, { barcode: '', product_name: '', quantity: 1, unit_cost: 0, total: 0 }]);
  };

  const handleRemoveItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    
    if (field === 'barcode') {
      const product = products.find(p => p.barcode === value);
      if (product) {
        newItems[index].product_name = product.name;
        newItems[index].unit_cost = product.purchase_price;
      }
    }
    
    if (field === 'quantity' || field === 'unit_cost') {
      newItems[index].total = parseFloat(newItems[index].quantity) * parseFloat(newItems[index].unit_cost);
    }
    
    setItems(newItems);
  };

  const calculateTotal = () => {
    return items.reduce((sum, item) => sum + item.total, 0);
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

    try {
      await axios.post(`${API}/purchases`, {
        supplier_name: selectedSupplier,
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
    setSelectedSupplier('');
    setItems([]);
  };

  const filteredProducts = products.filter(p =>
    searchProduct === '' ||
    p.barcode.toLowerCase().includes(searchProduct.toLowerCase()) ||
    p.name.toLowerCase().includes(searchProduct.toLowerCase())
  );

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
                <div className="space-y-2">
                  <Label htmlFor="supplier">Proveedor *</Label>
                  <Select value={selectedSupplier} onValueChange={setSelectedSupplier} required>
                    <SelectTrigger data-testid="purchase-supplier-select">
                      <SelectValue placeholder="Seleccionar proveedor" />
                    </SelectTrigger>
                    <SelectContent>
                      {suppliers.map((supplier) => (
                        <SelectItem key={supplier.name} value={supplier.name}>
                          {supplier.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Items de Compra</Label>
                    <Button type="button" variant="outline" size="sm" onClick={handleAddItem} data-testid="add-purchase-item-button">
                      <Plus className="h-3 w-3 mr-1" />
                      Agregar Item
                    </Button>
                  </div>
                  
                  {items.map((item, index) => (
                    <Card key={index}>
                      <CardContent className="p-4">
                        <div className="grid grid-cols-5 gap-2">
                          <div className="space-y-2">
                            <Label>Código de Barras</Label>
                            <Select
                              value={item.barcode}
                              onValueChange={(value) => handleItemChange(index, 'barcode', value)}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Seleccionar" />
                              </SelectTrigger>
                              <SelectContent>
                                {filteredProducts.map((product) => (
                                  <SelectItem key={product.barcode} value={product.barcode}>
                                    {product.barcode} - {product.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label>Producto</Label>
                            <Input value={item.product_name} disabled />
                          </div>
                          <div className="space-y-2">
                            <Label>Cantidad</Label>
                            <Input
                              type="number"
                              min="1"
                              value={item.quantity}
                              onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>Costo Unitario</Label>
                            <Input
                              type="number"
                              step="0.01"
                              value={item.unit_cost}
                              onChange={(e) => handleItemChange(index, 'unit_cost', e.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>Total</Label>
                            <div className="flex gap-2">
                              <Input value={item.total.toFixed(2)} disabled className="font-mono" />
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveItem(index)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <div className="border-t pt-4">
                  <div className="flex justify-between text-lg font-bold">
                    <span>Total Compra:</span>
                    <span className="font-mono" data-testid="purchase-total">${calculateTotal().toFixed(2)}</span>
                  </div>
                </div>
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
                <TableCell className="text-right font-mono font-bold">${purchase.total.toFixed(2)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{purchase.created_by}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(purchase.created_at).toLocaleString('es-ES')}
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