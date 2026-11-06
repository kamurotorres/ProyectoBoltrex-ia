import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import ExportMenu from '@/components/ExportMenu';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';
import { useServerSearch } from '@/hooks/useServerSearch';
import PurchaseDialog from '@/features/purchases/PurchaseDialog';
import PurchasesTable from '@/features/purchases/PurchasesTable';

const Purchases = () => {
  const { canCreate, canUpdate } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: compras paginadas en el servidor; proveedores y productos se buscan en el servidor.
  const [statusFilter, setStatusFilter] = useState('');
  const list = usePaginatedList(`${API}/purchases`, {
    params: statusFilter ? { status: statusFilter } : {},
    errorMessage: 'Error al cargar compras',
  });
  const purchases = list.items;
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmingId, setConfirmingId] = useState(null);

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
      await list.reload();
    } finally {
      setLoading(false);
    }
  };

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
    setSelectedSupplier({ name: purchase.supplier_name });
    setSupplierSearch(purchase.supplier_name);
    setItems(purchase.items.map(i => ({ ...i })));
    setProductSearch('');
    setDialogOpen(true);
  };

  const openViewDialog = (purchase) => {
    setDialogMode('readonly');
    setCurrentPurchase(purchase);
    setSelectedSupplier({ name: purchase.supplier_name });
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

    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (dialogMode === 'edit') {
        await api.put(`/purchases/${currentPurchase.purchase_number}`, payload);
        toast.success('Compra actualizada');
      } else {
        await api.post(`/purchases`, payload);
        toast.success('Compra creada en estado Borrador');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar compra'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // === Confirm purchase ===
  const handleConfirm = async (purchaseNumber) => {
    if (confirmingId) return;
    if (!(await confirm('¿Estás seguro de procesar esta compra?\nEsto actualizará el inventario y no se podrá editar.', { confirmLabel: 'Procesar compra' }))) return;
    setConfirmingId(purchaseNumber);
    try {
      await api.post(`/purchases/${purchaseNumber}/confirm`);
      notifyDataChanged();
      toast.success('Compra confirmada e inventario actualizado');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al confirmar compra'));
    } finally {
      setConfirmingId(null);
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
      <PurchaseDialog addProductToItems={addProductToItems} calculateTotal={calculateTotal} dialogDesc={dialogDesc} dialogMode={dialogMode} dialogOpen={dialogOpen} dialogTitle={dialogTitle} filteredProducts={filteredProducts} filteredSuppliers={filteredSuppliers} handleCloseDialog={handleCloseDialog} handleSelectSupplier={handleSelectSupplier} handleSubmit={handleSubmit} isReadonly={isReadonly} isSubmitting={isSubmitting} items={items} productInputRef={productInputRef} productSearch={productSearch} removeItem={removeItem} selectedSupplier={selectedSupplier} setDialogOpen={setDialogOpen} setItemQuantity={setItemQuantity} setItems={setItems} setProductSearch={setProductSearch} setSelectedSupplier={setSelectedSupplier} setShowProductDropdown={setShowProductDropdown} setShowSupplierDropdown={setShowSupplierDropdown} setSupplierSearch={setSupplierSearch} showProductDropdown={showProductDropdown} showSupplierDropdown={showSupplierDropdown} supplierInputRef={supplierInputRef} supplierSearch={supplierSearch} updateItemField={updateItemField} />

      {/* ======= PURCHASES TABLE ======= */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por código de compra o proveedor..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-purchases-input"
          />
        </div>
        <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)} aria-label="Estado" data-testid="purchases-status-filter">
          <option value="">Todas</option>
          <option value="borrador">Borradores</option>
          <option value="confirmado">Confirmadas</option>
        </select>
        {/* P2.33: Excel (Compras + Detalle) · PDF · CSV con la búsqueda y el estado activos */}
        <ExportMenu url={`${API}/purchases/export`} className="ml-auto" fallbackName="compras" testId="export-purchases-button"
                    params={{ ...(statusFilter ? { status: statusFilter } : {}), ...(list.search.trim() ? { search: list.search.trim() } : {}) }} />
      </div>
      <PurchasesTable canUpdate={canUpdate} confirmingId={confirmingId} handleConfirm={handleConfirm} openEditDialog={openEditDialog} openViewDialog={openViewDialog} purchases={purchases} />

      {purchases.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-purchases">
          No se encontraron compras registradas
        </div>
      )}
      <Pagination {...list.paginationProps} noun="compra(s)" testId="purchases-pagination" />
    </div>
  );
};

export default Purchases;
