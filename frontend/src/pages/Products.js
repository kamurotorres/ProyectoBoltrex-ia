import React, { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';
import { DEFAULT_PRICE_LIST } from '@/features/products/pricing';
import { useZodForm } from '@/hooks/useZodForm';
import { productSchema } from '@/lib/schemas';
import ProductDialog from '@/features/products/ProductDialog';
import ProductsTable from '@/features/products/ProductsTable';

const EMPTY = {
  barcode: '',
  name: '',
  description: '',
  category: '',
  purchase_price: '',
  // P1.16: el IVA inicia en 0 y el usuario lo ajusta según el producto.
  tax_rate: '0',
  min_stock: '',
  // P1.17: el precio 'default' es obligatorio: se precarga la fila.
  prices: [{ price_list_name: DEFAULT_PRICE_LIST, price: '' }],
};


const Products = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: productos paginados y buscados en el servidor.
  const list = usePaginatedList(`${API}/products`, { errorMessage: 'Error al cargar productos' });
  const [categories, setCategories] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentProduct, setCurrentProduct] = useState(null);
  // fase 6: formulario con react-hook-form + zod; los errores (también los de cada precio) salen debajo
  // de su campo. Las reglas de precios son las de features/products/pricing.js.
  const form = useZodForm(productSchema, EMPTY);
  const isSubmitting = form.submitting;
  const formData = form.watch();
  const setPrices = (prices) => form.setValue('prices', prices, { shouldValidate: form.formState.isSubmitted });

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

  const handleSubmit = form.submit(async (formData) => {
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
    }
  });

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
      form.reset({
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
      form.reset(EMPTY);
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
    setPrices([...formData.prices, { price_list_name: availableLists[0].name, price: '' }]);
  };

  const handleRemovePrice = (index) => {
    if (formData.prices[index]?.price_list_name === DEFAULT_PRICE_LIST) {
      toast.error("El precio de la lista 'default' es obligatorio: no se puede quitar.");
      return;
    }
    setPrices(formData.prices.filter((_, i) => i !== index));
  };

  const handlePriceChange = (index, field, value) => {
    const newPrices = formData.prices.map((p, i) => (i === index ? { ...p, [field]: value } : p));
    setPrices(newPrices);
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
          <ProductDialog activeLists={activeLists} availableLists={availableLists} categories={categories} dialogOpen={dialogOpen} editMode={editMode} formData={formData} handleAddPrice={handleAddPrice} handleCloseDialog={handleCloseDialog} handleOpenDialog={handleOpenDialog} handlePriceChange={handlePriceChange} handleRemovePrice={handleRemovePrice} handleSubmit={handleSubmit} isInactiveList={isInactiveList} isSubmitting={isSubmitting} priceLists={priceLists} setDialogOpen={setDialogOpen} form={form} />
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

      <ProductsTable canDelete={canDelete} canUpdate={canUpdate} filteredProducts={filteredProducts} handleDelete={handleDelete} handleOpenDialog={handleOpenDialog} />

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