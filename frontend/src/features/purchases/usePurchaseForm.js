import { useCallback, useState } from 'react';
import { api } from '@/api/client';
import { useZodForm } from '@/hooks/useZodForm';
import { useServerSearch } from '@/hooks/useServerSearch';
import { useBarcodeScan } from '@/hooks/useBarcodeScan';
import { purchaseSchema } from '@/lib/schemas';

// Formulario de compra (fase 6; rama compras-estilo-pos: página con el diseño del POS).
// - Proveedor y filas viven en react-hook-form (validados con purchaseSchema: errores debajo de cada parte).
// - `known`: costo y stock ACTUALES de cada producto (de las búsquedas o pedidos al abrir una compra), para
//   mostrar «antes $1.200» y «stock 8 → 10».
const EMPTY = { supplier: null, items: [] };

export function usePurchaseForm() {
  const form = useZodForm(purchaseSchema, EMPTY);
  const { supplier: selectedSupplier, items } = form.watch();
  const setValue = (name, value) => form.setValue(name, value, { shouldValidate: form.formState.isSubmitted });
  const setSelectedSupplier = (supplier) => setValue('supplier', supplier);
  const setItems = (next) => setValue('items', next);

  const [supplierSearch, setSupplierSearch] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [known, setKnown] = useState({});
  const remember = useCallback((found) => {
    setKnown((prev) => {
      const next = { ...prev };
      found.forEach((p) => { next[p.barcode] = { name: p.name, stock: p.stock, purchase_price: p.purchase_price }; });
      return next;
    });
  }, []);

  // P1.18: búsquedas en el servidor mientras se escribe (hook compartido, fase 5).
  const { results: supplierResults, searching: searchingSuppliers } = useServerSearch('/suppliers', supplierSearch, { pageSize: 10 });
  const { results: productResults, searching: searchingProducts } = useServerSearch('/products', productSearch, { pageSize: 8, onResults: remember });
  const filteredSuppliers = supplierSearch.length >= 2 ? supplierResults : [];
  const filteredProducts = productSearch.length >= 2 ? productResults : [];

  const handleSelectSupplier = (supplier) => {
    setSelectedSupplier(supplier);
    setSupplierSearch('');
  };
  const clearSupplier = () => {
    setSelectedSupplier(null);
    setSupplierSearch('');
  };

  // Mismas reglas de las filas que antes (fase 5/6): agregar suma 1 si ya está; el costo inicial es el actual.
  const addProductToItems = (product) => {
    remember([product]);
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
  };

  // Lector de código de barras (decisión 3.A).
  const scan = useBarcodeScan();
  const handleScan = async (code) => {
    const product = await scan(code, filteredProducts);
    if (product) addProductToItems(product);
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
    const qty = parseInt(value) || 0;   // eslint-disable-line radix -- igual que el original
    if (qty <= 0) return;
    updateItemField(barcode, 'quantity', qty);
  };
  /** Botones − / + (no baja de 1). */
  const stepItemQuantity = (barcode, delta) => {
    const item = items.find((i) => i.barcode === barcode);
    if (!item) return;
    setItemQuantity(barcode, Math.max(1, (parseInt(item.quantity) || 0) + delta));   // eslint-disable-line radix
  };
  /** Mientras se escribe la cantidad se permite dejarla vacía (al salir vuelve a 1). */
  const typeItemQuantity = (barcode, value) => {
    if (value === '') setItems(items.map(i => (i.barcode === barcode ? { ...i, quantity: '' } : i)));
    else setItemQuantity(barcode, value);
  };

  const removeItem = (barcode) => {
    setItems(items.filter(i => i.barcode !== barcode));
  };

  const calculateTotal = () => items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);
  const totalUnits = () => items.reduce((sum, item) => sum + (parseInt(item.quantity) || 0), 0);   // eslint-disable-line radix

  /** Deja el formulario vacío (compra nueva) o con los datos de una compra (editar / ver). */
  const load = async (purchase = null) => {
    form.reset(purchase
      ? { supplier: { name: purchase.supplier_name }, items: purchase.items.map(i => ({ ...i })) }
      : EMPTY);
    setSupplierSearch('');
    setProductSearch('');
    if (!purchase) return;
    // Costo y stock actuales de cada producto, y el contacto del proveedor (solo para mostrar).
    const found = await Promise.all(purchase.items.map((i) => api.get(`/products/${encodeURIComponent(i.barcode)}`)
      .then((r) => r.data).catch(() => null)));
    remember(found.filter(Boolean));
    api.get('/suppliers', { params: { search: purchase.supplier_name, page_size: 10 } }).then((r) => {
      const match = (r.data.items || []).find((s) => s.name === purchase.supplier_name);
      if (match) form.setValue('supplier', match);
    }).catch(() => {});
  };

  /** Lo que se envía al backend (igual que antes). */
  const toPayload = (values) => ({
    supplier_name: values.supplier.name,
    items: values.items.map(item => ({
      barcode: item.barcode,
      product_name: item.product_name,
      quantity: parseInt(item.quantity),   // eslint-disable-line radix -- igual que el original
      unit_cost: parseFloat(item.unit_cost),
      total: parseFloat(item.total)
    }))
  });

  const errors = form.errors;
  return {
    form, errors, load, toPayload, known,
    selectedSupplier, setSelectedSupplier, clearSupplier, items, setItems,
    supplierSearch, setSupplierSearch, filteredSuppliers, searchingSuppliers,
    productSearch, setProductSearch, filteredProducts, searchingProducts, handleScan,
    handleSelectSupplier, addProductToItems, updateItemField, setItemQuantity, stepItemQuantity, typeItemQuantity, removeItem,
    calculateTotal, totalUnits,
  };
}

export default usePurchaseForm;
