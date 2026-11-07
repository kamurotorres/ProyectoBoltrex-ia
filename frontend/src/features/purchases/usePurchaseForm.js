import { useEffect, useRef, useState } from 'react';
import { useZodForm } from '@/hooks/useZodForm';
import { useServerSearch } from '@/hooks/useServerSearch';
import { purchaseSchema } from '@/lib/schemas';

// Formulario de compra (mantenimiento fase 6). Junta en un solo lugar lo que antes eran ~15 estados sueltos
// de pages/Purchases.js (proveedor, buscadores, desplegables y filas); la lógica de las filas es la misma.
// - Proveedor y filas viven en react-hook-form (validados con purchaseSchema: errores debajo de cada parte).
// - Los buscadores y desplegables son estado de pantalla normal.
const EMPTY = { supplier: null, items: [] };

export function usePurchaseForm() {
  const form = useZodForm(purchaseSchema, EMPTY);
  const { supplier: selectedSupplier, items } = form.watch();
  const setValue = (name, value) => form.setValue(name, value, { shouldValidate: form.formState.isSubmitted });
  const setSelectedSupplier = (supplier) => setValue('supplier', supplier);
  const setItems = (next) => setValue('items', next);

  const [supplierSearch, setSupplierSearch] = useState('');
  const [showSupplierDropdown, setShowSupplierDropdown] = useState(false);
  const supplierInputRef = useRef(null);
  const [productSearch, setProductSearch] = useState('');
  const [showProductDropdown, setShowProductDropdown] = useState(false);
  const productInputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (supplierInputRef.current && !supplierInputRef.current.contains(event.target)) setShowSupplierDropdown(false);
      if (productInputRef.current && !productInputRef.current.contains(event.target)) setShowProductDropdown(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // P1.18: desplegables con búsqueda en el servidor (hook compartido, fase 5).
  const { results: supplierResults } = useServerSearch('/suppliers', supplierSearch, { pageSize: 10 });
  const { results: productResults } = useServerSearch('/products', productSearch, { pageSize: 8 });
  const filteredSuppliers = supplierSearch.length >= 2 ? supplierResults : [];
  const filteredProducts = productSearch.length >= 2 ? productResults : [];

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
    const qty = parseInt(value) || 0;   // eslint-disable-line radix -- igual que el original
    if (qty <= 0) return;
    updateItemField(barcode, 'quantity', qty);
  };

  const removeItem = (barcode) => {
    setItems(items.filter(i => i.barcode !== barcode));
  };

  const calculateTotal = () => items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);

  /** Deja el formulario vacío (compra nueva) o con los datos de una compra (editar / ver). */
  const load = (purchase = null) => {
    form.reset(purchase
      ? { supplier: { name: purchase.supplier_name }, items: purchase.items.map(i => ({ ...i })) }
      : EMPTY);
    setSupplierSearch(purchase ? purchase.supplier_name : '');
    setProductSearch('');
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
    form, errors, load, toPayload,
    selectedSupplier, setSelectedSupplier, items, setItems,
    supplierSearch, setSupplierSearch, showSupplierDropdown, setShowSupplierDropdown, supplierInputRef, filteredSuppliers,
    productSearch, setProductSearch, showProductDropdown, setShowProductDropdown, productInputRef, filteredProducts,
    handleSelectSupplier, addProductToItems, updateItemField, setItemQuantity, removeItem, calculateTotal,
  };
}

export default usePurchaseForm;
