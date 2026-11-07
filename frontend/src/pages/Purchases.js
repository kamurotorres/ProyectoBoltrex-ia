import React, { useState, useEffect } from 'react';
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
import PurchaseDialog from '@/features/purchases/PurchaseDialog';
import { usePurchaseForm } from '@/features/purchases/usePurchaseForm';
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
  const [confirmingId, setConfirmingId] = useState(null);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('create'); // create | edit | readonly
  const [currentPurchase, setCurrentPurchase] = useState(null);

  // Formulario (proveedor, buscadores y filas): fase 6, react-hook-form + zod en features/purchases/usePurchaseForm.
  const purchaseForm = usePurchaseForm();
  const isSubmitting = purchaseForm.form.submitting;

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      await list.reload();
    } finally {
      setLoading(false);
    }
  };

  // === Dialog open helpers ===
  const openCreateDialog = () => {
    setDialogMode('create');
    setCurrentPurchase(null);
    purchaseForm.load();
    setDialogOpen(true);
  };

  const openEditDialog = (purchase) => {
    setDialogMode('edit');
    setCurrentPurchase(purchase);
    purchaseForm.load(purchase);
    setDialogOpen(true);
  };

  const openViewDialog = (purchase) => {
    setDialogMode('readonly');
    setCurrentPurchase(purchase);
    purchaseForm.load(purchase);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setCurrentPurchase(null);
  };

  // === Submit (create / edit) ===
  // Proveedor elegido, al menos un producto y filas válidas: lo valida purchaseSchema (error debajo de cada parte).
  const handleSubmit = purchaseForm.form.submit(async (values) => {
    const payload = purchaseForm.toPayload(values);
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
    }
  });

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
      <PurchaseDialog purchaseForm={purchaseForm} dialogDesc={dialogDesc} dialogMode={dialogMode} dialogOpen={dialogOpen} dialogTitle={dialogTitle}
                      handleCloseDialog={handleCloseDialog} handleSubmit={handleSubmit} isReadonly={isReadonly} isSubmitting={isSubmitting}
                      setDialogOpen={setDialogOpen} />

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
