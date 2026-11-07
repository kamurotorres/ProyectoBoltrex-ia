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
import { useZodForm } from '@/hooks/useZodForm';
import { TextField } from '@/components/form/Field';
import { categorySchema } from '@/lib/schemas';

const EMPTY = { name: '', description: '' };

const Categories = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: paginadas y buscadas en el servidor (paginated=true; sin él, la lista completa para selectores).
  const list = usePaginatedList(`${API}/categories`, { params: { paginated: true }, errorMessage: 'Error al cargar categorías' });
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentCategory, setCurrentCategory] = useState(null);
  // fase 6: formulario con react-hook-form + zod (errores debajo de cada campo).
  const form = useZodForm(categorySchema, EMPTY);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    await list.reload();
    setLoading(false);
  };

  const handleSubmit = form.submit(async (formData) => {
    try {
      if (editMode) {
        await api.put(`/categories/${currentCategory.name}`, formData);
        toast.success('Categoría actualizada');
      } else {
        await api.post(`/categories`, formData);
        toast.success('Categoría creada');
      }
      fetchCategories();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar categoría'));
    }
  });
  const isSubmitting = form.submitting;

  const handleDelete = async (name) => {
    if (!(await confirm('¿Estás seguro de eliminar esta categoría?', { confirmLabel: 'Eliminar', destructive: true }))) return;
    try {
      await api.delete(`/categories/${name}`);
      toast.success('Categoría eliminada');
      fetchCategories();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar categoría'));
    }
  };

  const handleOpenDialog = (category = null) => {
    if (category) {
      setEditMode(true);
      setCurrentCategory(category);
      form.reset({ name: category.name, description: category.description || '' });
    } else {
      setEditMode(false);
      setCurrentCategory(null);
      form.reset(EMPTY);
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentCategory(null);
    form.reset(EMPTY);
  };

  const filteredCategories = list.items;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="categories-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Categorías</h1>
          <p className="text-muted-foreground mt-2">Gestiona las categorías de productos</p>
        </div>
        {canCreate('categories') && (
          <Button onClick={() => handleOpenDialog()} data-testid="create-category-button">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Categoría
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent data-testid="category-dialog">
            <DialogHeader>
              <DialogTitle>{editMode ? 'Editar Categoría' : 'Nueva Categoría'}</DialogTitle>
              <DialogDescription>
                {editMode ? 'Modifica los datos de la categoría' : 'Crea una nueva categoría de productos'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-4 py-4">
                {/* En edición el nombre no se cambia (igual que antes): solo se muestra. */}
                {editMode ? (
                  <div className="space-y-2">
                    <Label htmlFor="name">Nombre</Label>
                    <Input id="name" value={currentCategory?.name || ''} disabled data-testid="category-name-input" />
                  </div>
                ) : (
                  <TextField form={form} name="name" label="Nombre" data-testid="category-name-input" />
                )}
                <TextField form={form} name="description" label="Descripción" data-testid="category-description-input" />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSubmitting} data-testid="save-category-button">
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
            placeholder="Buscar categorías..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-categories-input"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCategories.map((category, index) => (
          <Card key={category.name} className="card-hover" data-testid={`category-card-${index}`}>
            <CardContent className="p-6">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-lg font-semibold">{category.name}</h3>
                <div className="flex gap-2">
                  {canUpdate('categories') && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenDialog(category)}
                      data-testid={`edit-category-${index}`}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                  {canDelete('categories') && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(category.name)}
                      data-testid={`delete-category-${index}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              {category.description && (
                <p className="text-sm text-muted-foreground">{category.description}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredCategories.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-categories">
          No se encontraron categorías
        </div>
      )}
      <Pagination {...list.paginationProps} noun="categoría(s)" testId="categories-pagination" />
    </div>
  );
};

export default Categories;