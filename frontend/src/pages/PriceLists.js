import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Plus, Search, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const PriceLists = () => {
  const { canCreate, canUpdate, canDelete } = usePermissions();
  const [priceLists, setPriceLists] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentPL, setCurrentPL] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true
  });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const response = await axios.get(`${API}/price-lists`);
      setPriceLists(response.data);
    } catch (error) {
      toast.error('Error al cargar listas de precios');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editMode) {
        await axios.put(`${API}/price-lists/${encodeURIComponent(currentPL.name)}`, formData);
        toast.success('Lista de precios actualizada');
      } else {
        await axios.post(`${API}/price-lists`, formData);
        toast.success('Lista de precios creada');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar');
    }
  };

  const handleOpenDialog = (pl = null) => {
    if (pl) {
      setEditMode(true);
      setCurrentPL(pl);
      setFormData({ name: pl.name, description: pl.description || '', is_active: pl.is_active });
    } else {
      setEditMode(false);
      setCurrentPL(null);
      setFormData({ name: '', description: '', is_active: true });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentPL(null);
  };

  const handleDelete = async (name) => {
    if (!window.confirm('¿Estás seguro de eliminar esta lista de precios?')) return;
    try {
      await axios.delete(`${API}/price-lists/${encodeURIComponent(name)}`);
      toast.success('Lista de precios eliminada');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    }
  };

  const filtered = priceLists.filter(pl =>
    search === '' || pl.name.toLowerCase().includes(search.toLowerCase())
  );

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
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nombre *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  data-testid="price-list-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Descripción</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  data-testid="price-list-description-input"
                />
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  data-testid="price-list-active-switch"
                />
                <Label htmlFor="is_active">Activa</Label>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>Cancelar</Button>
              <Button type="submit" data-testid="save-price-list-button">{editMode ? 'Actualizar' : 'Crear'}</Button>
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
            value={search}
            onChange={(e) => setSearch(e.target.value)}
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

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-price-lists">
          No se encontraron listas de precios
        </div>
      )}
    </div>
  );
};

export default PriceLists;
