import React, { useState, useEffect } from 'react';
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
import { Plus, Search, Edit, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';

// P1.16/P1.17: mismas reglas que el backend (core/pricing.py). El backend vuelve a validar.
const DEFAULT_PRICE_LIST = 'default';
const pricingProblem = ({ purchase_price, tax_rate, prices }) => {
  const cost = parseFloat(purchase_price);
  if (Number.isNaN(cost)) return 'El precio de compra debe ser un número.';
  if (cost < 0) return 'El precio de compra no puede ser negativo.';
  const iva = parseFloat(tax_rate);
  if (Number.isNaN(iva) || iva < 0 || iva > 100) return 'El IVA debe estar entre 0 y 100 %.';
  const rows = (prices || []).filter((p) => p.price_list_name || p.price !== '');
  if (rows.length === 0) return "No se puede crear un producto sin precios de venta. Agrega al menos el precio de la lista 'default'.";
  const seen = new Set();
  for (const p of rows) {
    if (!p.price_list_name) return 'Cada precio de venta debe tener su lista de precios.';
    if (seen.has(p.price_list_name)) return `La lista de precios '${p.price_list_name}' está repetida.`;
    seen.add(p.price_list_name);
    const price = parseFloat(p.price);
    if (Number.isNaN(price) || price <= 0) return `El precio de la lista '${p.price_list_name}' debe ser mayor a 0.`;
    if (price < cost) return `El precio de venta de la lista '${p.price_list_name}' no puede ser menor que el precio de compra.`;
  }
  if (!seen.has(DEFAULT_PRICE_LIST)) {
    return "El precio de la lista 'default' es obligatorio: es el que se cobra cuando el cliente tiene una lista para la que el producto no tiene precio.";
  }
  return null;
};

const Products = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: productos paginados y buscados en el servidor.
  const list = usePaginatedList(`${API}/products`, { errorMessage: 'Error al cargar productos' });
  const [categories, setCategories] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentProduct, setCurrentProduct] = useState(null);
  const [formData, setFormData] = useState({
    barcode: '',
    name: '',
    description: '',
    category: '',
    purchase_price: '',
    tax_rate: '0',
    min_stock: '',
    prices: [{ price_list_name: DEFAULT_PRICE_LIST, price: '' }]
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [categoriesRes, priceListsRes] = await Promise.all([
        api.get(`/categories`),
        api.get(`/price-lists`)
      ]);
      list.reload();
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
    if (isSubmitting) return;

    const problem = pricingProblem(formData);
    if (problem) {
      toast.error(problem);
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        ...formData,
        purchase_price: parseFloat(formData.purchase_price),
        tax_rate: parseFloat(formData.tax_rate),
        // P2.34: vacío = usa el stock mínimo general de Config. Sistema.
        min_stock: formData.min_stock === '' ? null : parseInt(formData.min_stock, 10),
        prices: formData.prices
          .filter(p => p.price_list_name || p.price !== '')
          .map(p => ({
            ...p,
            price: parseFloat(p.price)
          }))
      };

      if (editMode) {
        await api.put(`/products/${currentProduct.barcode}`, payload);
        toast.success('Producto actualizado');
      } else {
        await api.post(`/products`, payload);
        toast.success('Producto creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar producto'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (barcode) => {
    if (!(await confirm('¿Estás seguro de eliminar este producto?', { confirmLabel: 'Eliminar', destructive: true }))) return;
    try {
      await api.delete(`/products/${barcode}`);
      toast.success('Producto eliminado');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar producto'));
    }
  };

  // Las listas de precios se vuelven a pedir al abrir el formulario: una lista creada
  // (o activada/desactivada) en otra pestaña se refleja sin recargar la página.
  const refreshPriceLists = async () => {
    try {
      const res = await api.get(`/price-lists`);
      setPriceLists(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudieron cargar las listas de precios'));
    }
  };

  // 'default' siempre primero (y agregado si un producto antiguo no lo tenía).
  const withDefaultFirst = (prices) => {
    const def = prices.find((p) => p.price_list_name === DEFAULT_PRICE_LIST) || { price_list_name: DEFAULT_PRICE_LIST, price: '' };
    return [def, ...prices.filter((p) => p !== def && p.price_list_name !== DEFAULT_PRICE_LIST)];
  };

  const handleOpenDialog = (product = null) => {
    refreshPriceLists();
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
        min_stock: product.min_stock != null ? String(product.min_stock) : '',
        prices: withDefaultFirst((product.prices || []).map((p) => ({ ...p, price: String(p.price) }))),
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
        // P1.16: el IVA inicia en 0 y el usuario lo ajusta según el producto.
        tax_rate: '0',
        min_stock: '',
        // P1.17: el precio 'default' es obligatorio: se precarga la fila.
        prices: [{ price_list_name: DEFAULT_PRICE_LIST, price: '' }]
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentProduct(null);
  };

  // Listas activas que aún no tienen precio en el formulario. El máximo de precios es el
  // número de listas parametrizadas que envía el backend (no un número fijo).
  const activeLists = priceLists.filter((pl) => pl.is_active !== false);
  const usedLists = new Set(formData.prices.map((p) => p.price_list_name).filter(Boolean));
  const availableLists = activeLists.filter((pl) => !usedLists.has(pl.name));
  const isInactiveList = (name) => priceLists.some((pl) => pl.name === name && pl.is_active === false);

  const handleAddPrice = () => {
    if (availableLists.length === 0) {
      toast.error(`Ya agregaste todas las listas de precios activas (${activeLists.length}).`);
      return;
    }
    // La nueva fila ya trae la primera lista libre: nunca nace repetida ni vacía.
    setFormData({
      ...formData,
      prices: [...formData.prices, { price_list_name: availableLists[0].name, price: '' }]
    });
  };

  const handleRemovePrice = (index) => {
    if (formData.prices[index]?.price_list_name === DEFAULT_PRICE_LIST) {
      toast.error("El precio de la lista 'default' es obligatorio: no se puede quitar.");
      return;
    }
    setFormData({
      ...formData,
      prices: formData.prices.filter((_, i) => i !== index)
    });
  };

  const handlePriceChange = (index, field, value) => {
    const newPrices = formData.prices.map((p, i) => (i === index ? { ...p, [field]: value } : p));
    setFormData({ ...formData, prices: newPrices });
  };

  const filteredProducts = list.items;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="products-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Productos</h1>
          <p className="text-muted-foreground mt-2">Gestiona tu catálogo de productos</p>
        </div>
        {canCreate('products') && (
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
                      min="0"
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
                      min="0"
                      max="100"
                      value={formData.tax_rate}
                      onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
                      required
                      data-testid="product-tax-rate-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="min_stock">Stock mínimo (opcional)</Label>
                  <Input
                    id="min_stock"
                    type="number"
                    step="1"
                    min="0"
                    placeholder="Usa el general de Config. Sistema"
                    value={formData.min_stock}
                    onChange={(e) => setFormData({ ...formData, min_stock: e.target.value })}
                    data-testid="product-min-stock-input"
                  />
                  <p className="text-xs text-muted-foreground">Avisa «bajo stock» cuando quedan menos unidades que este número.</p>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <div>
                      <Label>Precios de Venta *</Label>
                      <p className="text-xs text-muted-foreground mt-1">
                        El precio <span className="font-mono">default</span> es obligatorio y se cobra a clientes cuya lista no tenga precio.
                        Cada precio debe ser mayor o igual al precio de compra.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleAddPrice}
                      disabled={availableLists.length === 0}
                      title={availableLists.length === 0 ? `Ya agregaste todas las listas de precios activas (${activeLists.length})` : undefined}
                      data-testid="add-price-button"
                    >
                      <Plus className="h-3 w-3 mr-1" />
                      Agregar Precio ({formData.prices.filter((p) => !isInactiveList(p.price_list_name)).length}/{activeLists.length})
                    </Button>
                  </div>
                  {formData.prices.map((price, index) => {
                    const isDefault = price.price_list_name === DEFAULT_PRICE_LIST && index === 0;
                    const inactive = isInactiveList(price.price_list_name);
                    // Opciones: la lista de esta fila + las activas que no usa ninguna otra fila.
                    const options = [
                      ...(price.price_list_name ? [priceLists.find((pl) => pl.name === price.price_list_name) || { name: price.price_list_name }] : []),
                      ...availableLists,
                    ];
                    return (
                      <div key={`${index}-${price.price_list_name}`} className="flex gap-2 items-center" data-testid={`price-row-${index}`}>
                        {isDefault ? (
                          <div className="flex h-9 w-full items-center rounded-md border border-input bg-muted/40 px-3 text-sm" title="Obligatoria: se cobra a clientes cuya lista no tenga precio">
                            default <span className="ml-1 text-xs text-muted-foreground">(obligatoria)</span>
                          </div>
                        ) : (
                          <Select
                            value={price.price_list_name}
                            onValueChange={(value) => handlePriceChange(index, 'price_list_name', value)}
                          >
                            <SelectTrigger data-testid={`price-list-select-${index}`}>
                              <SelectValue placeholder="Lista de Precios" />
                            </SelectTrigger>
                            <SelectContent>
                              {options.map((pl) => (
                                <SelectItem key={pl.name} value={pl.name} disabled={pl.is_active === false && pl.name !== price.price_list_name}>
                                  {pl.name}{pl.is_active === false ? ' (inactiva)' : ''}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="Precio"
                          value={price.price}
                          onChange={(e) => handlePriceChange(index, 'price', e.target.value)}
                          data-testid={`price-input-${index}`}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemovePrice(index)}
                          disabled={isDefault}
                          title={isDefault ? 'La lista default es obligatoria' : inactive ? 'Lista inactiva: puedes quitar este precio' : 'Quitar precio'}
                          className={isDefault ? 'invisible' : ''}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    );
                  })}
                  {formData.prices.some((p) => isInactiveList(p.price_list_name)) && (
                    <p className="text-xs text-amber-500" data-testid="inactive-price-note">
                      Hay precios en listas inactivas: se conservan, pero no se cobran mientras la lista siga inactiva. Puedes quitarlos.
                    </p>
                  )}
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSubmitting} data-testid="save-product-button">
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editMode ? 'Actualizando...' : 'Creando...'}
                    </>
                  ) : (
                    editMode ? 'Actualizar' : 'Crear'
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
        )}
      </div>

      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar por código o nombre..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
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
                    {canUpdate('products') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenDialog(product)}
                        data-testid={`edit-product-${index}`}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                    )}
                    {canDelete('products') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(product.barcode)}
                        data-testid={`delete-product-${index}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {filteredProducts.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-products">
          No se encontraron productos
        </div>
      )}
      <Pagination {...list.paginationProps} noun="producto(s)" testId="products-pagination" />
    </div>
  );
};

export default Products;