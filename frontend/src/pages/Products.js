import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Plus, Search, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const Products = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentProduct, setCurrentProduct] = useState(null);
  const [formData, setFormData] = useState({
    barcode: '',
    name: '',
    description: '',
    category: '',
    purchase_price: '',
    tax_rate: '19',
    prices: []
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [productsRes, categoriesRes, priceListsRes] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/categories`),
        axios.get(`${API}/price-lists`)
      ]);
      setProducts(productsRes.data);
      setCategories(categoriesRes.data);
      setPriceLists(priceListsRes.data);
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        purchase_price: parseFloat(formData.purchase_price),
        tax_rate: parseFloat(formData.tax_rate),
        prices: formData.prices.map(p => ({
          ...p,
          price: parseFloat(p.price)
        }))
      };

      if (editMode) {
        await axios.put(`${API}/products/${currentProduct.barcode}`, payload);
        toast.success('Producto actualizado');
      } else {
        await axios.post(`${API}/products`, payload);
        toast.success('Producto creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar producto');
    }
  };

  const handleDelete = async (barcode) => {
    if (!window.confirm('¿Estás seguro de eliminar este producto?')) return;
    try {
      await axios.delete(`${API}/products/${barcode}`);
      toast.success('Producto eliminado');
      fetchData();
    } catch (error) {
      toast.error('Error al eliminar producto');
    }
  };

  const handleOpenDialog = (product = null) => {
    if (product) {
      setEditMode(true);
      setCurrentProduct(product);
      setFormData({
        barcode: product.barcode,
        name: product.name,
        description: product.description || '',
        category: product.category,
        purchase_price: product.purchase_price.toString(),
        tax_rate: product.tax_rate.toString(),
        prices: product.prices
      });
    } else {
      setEditMode(false);
      setCurrentProduct(null);
      setFormData({
        barcode: '',
        name: '',
        description: '',
        category: '',
        purchase_price: '',
        tax_rate: '19',
        prices: []
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentProduct(null);
  };

  const handleAddPrice = () => {
    if (formData.prices.length >= priceLists.length) {
      toast.error('Ya agregaste todas las listas de precios disponibles');
      return;
    }
    setFormData({
      ...formData,
      prices: [...formData.prices, { price_list_name: '', price: '' }]
    });
  };

  const handleRemovePrice = (index) => {
    setFormData({
      ...formData,
      prices: formData.prices.filter((_, i) => i !== index)
    });
  };

  const handlePriceChange = (index, field, value) => {
    const newPrices = [...formData.prices];
    newPrices[index][field] = value;
    setFormData({ ...formData, prices: newPrices });
  };

  const filteredProducts = products.filter(p =>
    search === '' ||
    p.barcode.toLowerCase().includes(search.toLowerCase()) ||
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="products-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Productos</h1>
          <p className="text-muted-foreground mt-2">Gestiona tu catálogo de productos</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => handleOpenDialog()} data-testid="create-product-button">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Producto
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="product-dialog">
            <DialogHeader>
              <DialogTitle>{editMode ? 'Editar Producto' : 'Nuevo Producto'}</DialogTitle>
              <DialogDescription>
                {editMode ? 'Modifica los datos del producto' : 'Crea un nuevo producto en el catálogo'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="barcode">Código de Barras *</Label>
                    <Input
                      id="barcode"
                      value={formData.barcode}
                      onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                      required
                      disabled={editMode}
                      data-testid="product-barcode-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="name">Nombre *</Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      data-testid="product-name-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Descripción</Label>
                  <Input
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    data-testid="product-description-input"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="category">Categoría *</Label>
                    <Select
                      value={formData.category}
                      onValueChange={(value) => setFormData({ ...formData, category: value })}
                      required
                    >
                      <SelectTrigger data-testid="product-category-select">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map((cat) => (
                          <SelectItem key={cat.name} value={cat.name}>
                            {cat.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="purchase_price">Precio Compra *</Label>
                    <Input
                      id="purchase_price"
                      type="number"
                      step="0.01"
                      value={formData.purchase_price}
                      onChange={(e) => setFormData({ ...formData, purchase_price: e.target.value })}
                      required
                      data-testid="product-purchase-price-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="tax_rate">IVA (%) *</Label>
                    <Input
                      id="tax_rate"
                      type="number"
                      step="0.01"
                      value={formData.tax_rate}
                      onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
                      required
                      data-testid="product-tax-rate-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Precios de Venta</Label>
                    <Button type="button" variant="outline" size="sm" onClick={handleAddPrice} data-testid="add-price-button">
                      <Plus className="h-3 w-3 mr-1" />
                      Agregar Precio
                    </Button>
                  </div>
                  {formData.prices.map((price, index) => (
                    <div key={index} className="flex gap-2">
                      <Select
                        value={price.price_list_name}
                        onValueChange={(value) => handlePriceChange(index, 'price_list_name', value)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Lista de Precios" />
                        </SelectTrigger>
                        <SelectContent>
                          {priceLists.map((pl) => (
                            <SelectItem key={pl.name} value={pl.name}>
                              {pl.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="Precio"
                        value={price.price}
                        onChange={(e) => handlePriceChange(index, 'price', e.target.value)}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRemovePrice(index)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" data-testid="save-product-button">
                  {editMode ? 'Actualizar' : 'Crear'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar por código o nombre..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-products-input"
          />
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Categoría</TableHead>
              <TableHead className="text-right font-mono">Stock</TableHead>
              <TableHead className="text-right font-mono">P. Compra</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredProducts.map((product, index) => (
              <TableRow key={product.barcode} data-testid={`product-row-${index}`}>
                <TableCell className="font-mono">{product.barcode}</TableCell>
                <TableCell>{product.name}</TableCell>
                <TableCell>{product.category}</TableCell>
                <TableCell className="text-right font-mono">{product.stock}</TableCell>
                <TableCell className="text-right font-mono">${product.purchase_price.toFixed(2)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenDialog(product)}
                      data-testid={`edit-product-${index}`}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(product.barcode)}
                      data-testid={`delete-product-${index}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {filteredProducts.length === 0 && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-products">
          No se encontraron productos
        </div>
      )}
    </div>
  );
};

export default Products;