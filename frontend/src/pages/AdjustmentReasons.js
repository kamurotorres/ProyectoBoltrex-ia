import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Plus, Search, Edit, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';

// P2.32: catálogo de motivos de los ajustes de inventario (como Categorías).
export const ADJUSTMENT_KINDS = [
  { key: 'entrada', label: 'Entrada', hint: 'suma al stock' },
  { key: 'salida', label: 'Salida', hint: 'resta del stock' },
  { key: 'conteo', label: 'Conteo físico', hint: 'deja el stock en lo contado' },
];
const EMPTY = { name: '', description: '', applies_to: ['salida'], requires_note: false, is_active: true };

const AdjustmentReasons = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  const list = usePaginatedList(`${API}/adjustment-reasons`, { params: { paginated: true }, errorMessage: 'Error al cargar los motivos' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [current, setCurrent] = useState(null);
  const [formData, setFormData] = useState(EMPTY);

  const openDialog = (reason = null) => {
    setCurrent(reason);
    setFormData(reason ? {
      name: reason.name, description: reason.description || '', applies_to: reason.applies_to || [],
      requires_note: !!reason.requires_note, is_active: reason.is_active !== false,
    } : EMPTY);
    setDialogOpen(true);
  };

  const toggleKind = (key) => {
    const has = formData.applies_to.includes(key);
    setFormData({ ...formData, applies_to: has ? formData.applies_to.filter((k) => k !== key) : [...formData.applies_to, key] });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    if (!formData.name.trim()) {
      toast.error('Escribe el nombre del motivo.');
      return;
    }
    if (formData.applies_to.length === 0) {
      toast.error('Marca al menos un tipo de ajuste (entrada, salida o conteo) para el motivo.');
      return;
    }
    setIsSubmitting(true);
    try {
      if (current) {
        await api.put(`/adjustment-reasons/${encodeURIComponent(current.name)}`, formData);
        toast.success('Motivo actualizado');
      } else {
        await api.post(`/adjustment-reasons`, formData);
        toast.success('Motivo creado');
      }
      setDialogOpen(false);
      list.reload();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar el motivo'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (reason) => {
    if (!(await confirm(`¿Eliminar el motivo "${reason.name}"?`, { confirmLabel: 'Eliminar', destructive: true }))) return;
    try {
      await api.delete(`/adjustment-reasons/${encodeURIComponent(reason.name)}`);
      toast.success('Motivo eliminado');
      list.reload();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar el motivo'));
    }
  };

  const kindLabel = (k) => ADJUSTMENT_KINDS.find((x) => x.key === k)?.label || k;

  return (
    <div data-testid="adjustment-reasons-page">
      <div className="flex justify-between items-center mb-8 gap-4 flex-wrap">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Motivos de Ajuste</h1>
          <p className="text-muted-foreground mt-2">Motivos que se eligen al ajustar el inventario (merma, daño, conteo…)</p>
        </div>
        {canCreate('adjustment-reasons') && (
          <Button onClick={() => openDialog()} data-testid="create-reason-button">
            <Plus className="h-4 w-4 mr-2" />
            Nuevo Motivo
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="reason-dialog">
          <DialogHeader>
            <DialogTitle>{current ? 'Editar Motivo' : 'Nuevo Motivo'}</DialogTitle>
            <DialogDescription>
              {current ? 'Los ajustes ya hechos conservan el nombre que tenía el motivo.' : 'Crea un motivo para los ajustes de inventario'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="reason-name">Nombre *</Label>
                <Input id="reason-name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                       data-testid="reason-name-input" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reason-description">Descripción</Label>
                <Input id="reason-description" value={formData.description}
                       onChange={(e) => setFormData({ ...formData, description: e.target.value })} data-testid="reason-description-input" />
              </div>
              <div className="space-y-2">
                <Label>Se puede usar en *</Label>
                <div className="flex flex-wrap gap-2">
                  {ADJUSTMENT_KINDS.map((k) => (
                    <button key={k.key} type="button" onClick={() => toggleKind(k.key)}
                            className={`rounded-full border px-3 py-1 text-sm ${formData.applies_to.includes(k.key) ? 'bg-primary text-primary-foreground border-primary' : 'border-border text-muted-foreground hover:bg-muted'}`}
                            data-testid={`reason-kind-${k.key}`}>
                      {k.label}
                    </button>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-3">
                <Switch checked={formData.requires_note} onCheckedChange={(v) => setFormData({ ...formData, requires_note: v })}
                        data-testid="reason-requires-note" />
                <span className="text-sm">Exigir observación al usarlo</span>
              </label>
              <label className="flex items-center gap-3">
                <Switch checked={formData.is_active} onCheckedChange={(v) => setFormData({ ...formData, is_active: v })}
                        data-testid="reason-active" />
                <span className="text-sm">Activo (se puede elegir en los ajustes)</span>
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={isSubmitting} data-testid="save-reason-button">
                {isSubmitting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Guardando...</> : (current ? 'Actualizar' : 'Crear')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <div className="mb-6 relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input placeholder="Buscar motivos..." value={list.search} onChange={(e) => list.setSearch(e.target.value)}
               className="pl-10" data-testid="search-reasons-input" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {list.items.map((reason, index) => (
          <Card key={reason.name} className={`card-hover ${reason.is_active === false ? 'opacity-60' : ''}`} data-testid={`reason-card-${index}`}>
            <CardContent className="p-6">
              <div className="flex justify-between items-start mb-2 gap-2">
                <h3 className="text-lg font-semibold">
                  {reason.name}
                  {reason.is_active === false && <span className="ml-2 text-xs font-normal text-muted-foreground">(inactivo)</span>}
                </h3>
                <div className="flex gap-1">
                  {canUpdate('adjustment-reasons') && (
                    <Button variant="ghost" size="icon" onClick={() => openDialog(reason)} data-testid={`edit-reason-${index}`}>
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                  {canDelete('adjustment-reasons') && (
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(reason)} data-testid={`delete-reason-${index}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              {reason.description && <p className="text-sm text-muted-foreground mb-3">{reason.description}</p>}
              <div className="flex flex-wrap gap-1">
                {(reason.applies_to || []).map((k) => (
                  <span key={k} className="text-xs px-2 py-0.5 rounded-full bg-muted">{kindLabel(k)}</span>
                ))}
                {reason.requires_note && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400">Exige observación</span>}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {list.items.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground">No se encontraron motivos</div>
      )}
      <Pagination {...list.paginationProps} noun="motivo(s)" testId="reasons-pagination" />
    </div>
  );
};

export default AdjustmentReasons;
