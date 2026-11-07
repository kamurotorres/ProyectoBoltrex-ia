import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, Truck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FieldError } from '@/components/form/Field';
import PartySearchCard from '@/components/commerce/PartySearchCard';
import ProductSearchCard from '@/components/commerce/ProductSearchCard';
import { useConfirm } from '@/components/ConfirmDialog';
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/api/client';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { money, number } from '@/lib/format';
import { usePurchaseForm } from '@/features/purchases/usePurchaseForm';
import PurchaseItemsSection from '@/features/purchases/PurchaseItemsSection';
import { CONFIRM_QUESTION, notifyConfirmResult } from '@/features/purchases/confirmResult';

// Compra nueva / editar borrador / ver confirmada — rama compras-estilo-pos: página completa con el diseño del POS
// (1. Proveedor · 2. Agregar productos con lector · 3. Detalle con − / +, costo antes/ahora y stock → después).
//   /purchases/nueva            → compra nueva
//   /purchases/PUR-000001       → editar (borrador) o ver (confirmada / sin permiso de editar)
const PurchaseEditor = () => {
  const { purchaseNumber } = useParams();
  const isNew = !purchaseNumber;
  const navigate = useNavigate();
  const confirm = useConfirm();
  const { canCreate, canUpdate } = usePermissions();
  const purchaseForm = usePurchaseForm();
  const [purchase, setPurchase] = useState(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(null);   // null | 'draft' | 'process'

  useEffect(() => {
    let cancelled = false;
    if (isNew) { purchaseForm.load(); return undefined; }
    setLoading(true);
    api.get(`/purchases/${encodeURIComponent(purchaseNumber)}`).then((r) => {
      if (cancelled) return;
      setPurchase(r.data);
      purchaseForm.load(r.data);
    }).catch((error) => {
      toast.error(getErrorMessage(error, 'No se pudo cargar la compra'));
      navigate('/purchases');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [purchaseNumber]);

  const confirmed = purchase?.status === 'confirmado';
  const allowedToSave = isNew ? canCreate('purchases') : canUpdate('purchases');
  const readonly = confirmed || !allowedToSave;
  const { selectedSupplier, errors } = purchaseForm;

  /** Crea o actualiza el borrador. Devuelve su número (o null si falló: ya mostró el error). */
  const saveDraft = async (values) => {
    const payload = purchaseForm.toPayload(values);
    try {
      if (isNew) return (await api.post('/purchases', payload)).data.purchase_number;
      await api.put(`/purchases/${encodeURIComponent(purchaseNumber)}`, payload);
      return purchaseNumber;
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar compra'));
      return null;
    }
  };

  const onSaveDraft = purchaseForm.form.submit(async (values) => {
    setSaving('draft');
    const number_ = await saveDraft(values);
    setSaving(null);
    if (!number_) return;
    toast.success(isNew ? `Compra ${number_} creada en estado Borrador` : 'Compra actualizada');
    navigate('/purchases');
  });

  const onSaveAndProcess = purchaseForm.form.submit(async (values) => {
    if (!(await confirm(CONFIRM_QUESTION, { confirmLabel: 'Guardar y procesar' }))) return;
    setSaving('process');
    const number_ = await saveDraft(values);
    if (!number_) { setSaving(null); return; }
    try {
      const res = await api.post(`/purchases/${encodeURIComponent(number_)}/confirm`);
      notifyDataChanged();
      notifyConfirmResult(res.data, number_);
      navigate('/purchases');
    } catch (error) {
      // El borrador sí quedó guardado: se abre para reintentar.
      toast.error(`La compra ${number_} quedó guardada como borrador, pero no se pudo procesar: ${getErrorMessage(error, 'error desconocido')}`);
      if (isNew) navigate(`/purchases/${encodeURIComponent(number_)}`, { replace: true });
    } finally {
      setSaving(null);
    }
  });

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  const title = isNew ? 'Nueva Compra' : confirmed ? `Compra ${purchaseNumber}` : readonly ? `Compra ${purchaseNumber}` : `Editar Compra ${purchaseNumber}`;
  const subtitle = isNew ? 'Se guarda como borrador; al procesarla entra al inventario'
    : confirmed ? `Procesada · ${money(purchase?.total)} · registrada por ${purchase?.created_by}`
      : readonly ? 'Borrador (solo lectura: no tienes permiso para editar compras)' : 'Borrador: puedes cambiarla antes de procesarla';

  return (
    <div data-testid="purchase-editor-page" className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">{title}</h1>
          <p className="text-muted-foreground mt-2">{subtitle}</p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/purchases" data-testid="back-to-purchases"><ArrowLeft className="h-4 w-4 mr-2" />Volver a Compras</Link>
        </Button>
      </div>

      <PartySearchCard
        step={1}
        title="Seleccionar Proveedor"
        icon={Truck}
        selected={!!selectedSupplier}
        selectedTitle={selectedSupplier?.name}
        selectedLines={selectedSupplier && (
          <>
            {selectedSupplier.contact_name && <p className="text-sm text-muted-foreground">{selectedSupplier.contact_name}</p>}
            {selectedSupplier.phone && <p className="text-xs text-muted-foreground font-mono">{selectedSupplier.phone}</p>}
          </>
        )}
        onClear={readonly ? null : purchaseForm.clearSupplier}
        changeLabel="Cambiar Proveedor"
        hint="Busca y selecciona el proveedor de esta compra"
        placeholder="Buscar proveedor por nombre... (mínimo 2 caracteres)"
        query={purchaseForm.supplierSearch}
        onQueryChange={purchaseForm.setSupplierSearch}
        results={purchaseForm.filteredSuppliers}
        searching={purchaseForm.searchingSuppliers}
        resultKey={(s) => s.name}
        renderResult={(s) => ({
          title: s.name,
          subtitle: s.contact_name || '',
          side: s.phone ? <p className="text-xs text-muted-foreground">{s.phone}</p> : null,
        })}
        onSelect={purchaseForm.handleSelectSupplier}
        noun="proveedores"
        inputTestId="supplier-search-input"
        rowTestId="purchase-supplier"
      >
        <FieldError error={errors.supplier} id="purchase-supplier-error" />
      </PartySearchCard>

      {!readonly && (
        <ProductSearchCard
          step={2}
          enabled
          query={purchaseForm.productSearch}
          onQueryChange={purchaseForm.setProductSearch}
          onScan={purchaseForm.handleScan}
          results={purchaseForm.filteredProducts}
          searching={purchaseForm.searchingProducts}
          onAdd={purchaseForm.addProductToItems}
          renderSide={(product) => (
            <>
              <p className="font-bold text-lg font-mono text-primary">{money(product.purchase_price)}</p>
              <p className="text-xs text-muted-foreground">Costo actual · Stock: {number(product.stock)}</p>
            </>
          )}
          inListLabel={(product) => {
            const line = purchaseForm.items.find((i) => i.barcode === product.barcode);
            return line ? `En la compra: ${line.quantity}` : null;
          }}
          inputTestId="product-search-input"
          rowTestId="purchase-product"
        />
      )}

      <PurchaseItemsSection
        purchaseForm={purchaseForm}
        step={readonly ? 2 : 3}
        readonly={readonly}
        canSave={!!selectedSupplier && purchaseForm.items.length > 0}
        canProcess={!!selectedSupplier && purchaseForm.items.length > 0 && canUpdate('purchases')}
        saving={saving}
        onSaveDraft={onSaveDraft}
        onSaveAndProcess={onSaveAndProcess}
      />
    </div>
  );
};

export default PurchaseEditor;
