import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Plus, Search, Edit, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';
import { useZodForm } from '@/hooks/useZodForm';
import { SwitchField, TextField } from '@/components/form/Field';
import { priceListSchema } from '@/lib/schemas';

const EMPTY = { name: '', description: '', is_active: true };

const PriceLists = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: paginadas y buscadas en el servidor (paginated=true; sin él, la lista completa para selectores).
  const list = usePaginatedList(`${API}/price-lists`, { params: { paginated: true }, errorMessage: 'Error al cargar listas de precios' });
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentPL, setCurrentPL] = useState(null);
  // fase 6: formulario con react-hook-form + zod (errores debajo de cada campo).
  const form = useZodForm(priceListSchema, EMPTY);
  const isSubmitting = form.submitting;

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    await list.reload();
    setLoading(false);
  };

  const handleSubmit = form.submit(async (formData) => {
    try {
      if (editMode) {
        await api.put(`/price-lists/${encodeURIComponent(currentPL.name)}`, formData);
        toast.success('Lista de precios actualizada');
      } else {
        await api.post(`/price-lists`, formData);
        toast.success('Lista de precios creada');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar'));
    }
  });

  const handleOpenDialog = (pl = null) => {
    if (pl) {
      setEditMode(true);
      setCurrentPL(pl);
      form.reset({ name: pl.name, description: pl.description || '', is_active: pl.is_active });
    } else {
      setEditMode(false);
      setCurrentPL(null);
      form.reset(EMPTY);
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentPL(null);
  };

  const handleDelete = async (name) => {
    if (!(await confirm('¿Estás seguro de eliminar esta lista de precios?', { confirmLabel: 'Eliminar', destructive: true }))) return;
    try {
      await api.delete(`/price-lists/${encodeURIComponent(name)}`);
      toast.success('Lista de precios eliminada');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar'));
    }
  };

  const filtered = list.items;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="price-lists-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Listas de Precios</h1>
          <p className="text-muted-foreground mt-2">Gestiona las listas de precios del sistema</p>
        </div>
        {canCreate('price-lists') && (
          <Button onClick={() => handleOpenDialog()} data-testid="create-price-list-button">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Lista
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="price-list-dialog">
          <DialogHeader>
            <DialogTitle>{editMode ? 'Editar Lista de Precios' : 'Nueva Lista de Precios'}</DialogTitle>
            <DialogDescription>{editMode ? 'Modifica los datos de la lista' : 'Crea una nueva lista de precios'}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4 py-4">
              <TextField form={form} name="name" label="Nombre *" data-testid="price-list-name-input" />
              <TextField form={form} name="description" label="Descripción" data-testid="price-list-description-input" />
              <SwitchField form={form} name="is_active" id="is_active" label="Activa" data-testid="price-list-active-switch" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>Cancelar</Button>
              <Button type="submit" disabled={isSubmitting} data-testid="save-price-list-button">
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

      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar listas de precios..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-price-lists-input"
          />
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((pl, index) => (
              <TableRow key={index} data-testid={`price-list-row-${index}`}>
                <TableCell className="font-semibold">{pl.name}</TableCell>
                <TableCell className="text-muted-foreground">{pl.description || '-'}</TableCell>
                <TableCell>
                  <Badge variant={pl.is_active ? 'default' : 'secondary'}>
                    {pl.is_active ? 'Activa' : 'Inactiva'}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    {canUpdate('price-lists') && (
                      <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(pl)} data-testid={`edit-price-list-${index}`}>
                        <Edit className="h-4 w-4" />
                      </Button>
                    )}
                    {canDelete('price-lists') && (
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(pl.name)} data-testid={`delete-price-list-${index}`}>
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

      {filtered.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-price-lists">
          No se encontraron listas de precios
        </div>
      )}
      <Pagination {...list.paginationProps} noun="lista(s) de precios" testId="price-lists-pagination" />
    </div>
  );
};

export default PriceLists;
