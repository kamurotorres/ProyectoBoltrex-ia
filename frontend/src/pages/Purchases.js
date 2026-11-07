import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { CONFIRM_QUESTION, notifyConfirmResult } from '@/features/purchases/confirmResult';
import PurchasesTable from '@/features/purchases/PurchasesTable';

const Purchases = () => {
  const { canCreate, canUpdate } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: compras paginadas en el servidor.
  const [statusFilter, setStatusFilter] = useState('');
  const list = usePaginatedList(`${API}/purchases`, {
    params: statusFilter ? { status: statusFilter } : {},
    errorMessage: 'Error al cargar compras',
  });
  const purchases = list.items;
  const [loading, setLoading] = useState(true);
  const [confirmingId, setConfirmingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      await list.reload();
    } finally {
      setLoading(false);
    }
  };

  // Rama compras-estilo-pos: crear, editar y ver se hacen en la página completa (pages/PurchaseEditor.js).
  const openCreate = () => navigate('/purchases/nueva');
  const openPurchase = (purchase) => navigate(`/purchases/${encodeURIComponent(purchase.purchase_number)}`);

  // === Procesar desde el listado (avisa costos cambiados y precios a revisar, decisión 2.A) ===
  const handleConfirm = async (purchaseNumber) => {
    if (confirmingId) return;
    if (!(await confirm(CONFIRM_QUESTION, { confirmLabel: 'Procesar compra' }))) return;
    setConfirmingId(purchaseNumber);
    try {
      const res = await api.post(`/purchases/${purchaseNumber}/confirm`);
      notifyDataChanged();
      notifyConfirmResult(res.data, purchaseNumber);
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al confirmar compra'));
    } finally {
      setConfirmingId(null);
    }
  };

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="purchases-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Compras</h1>
          <p className="text-muted-foreground mt-2">Registro de compras a proveedores</p>
        </div>
        {canCreate('purchases') && (
          <Button onClick={openCreate} data-testid="create-purchase-button">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Compra
          </Button>
        )}
      </div>

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
      <PurchasesTable canUpdate={canUpdate} confirmingId={confirmingId} handleConfirm={handleConfirm} openEditDialog={openPurchase} openViewDialog={openPurchase} purchases={purchases} />

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
