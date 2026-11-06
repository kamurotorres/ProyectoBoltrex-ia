import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Search, Edit, MapPin, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';

const Clients = () => {
  const { canCreate, canUpdate, canDelete, isAdmin } = usePermissions();
  const money = (v) => `$${Number(v || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 })}`;
  // P1.18: clientes paginados y buscados en el servidor.
  const list = usePaginatedList(`${API}/clients`, { errorMessage: 'Error al cargar clientes' });
  const [documentTypes, setDocumentTypes] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentClient, setCurrentClient] = useState(null);
  const [formData, setFormData] = useState({
    document_type: '',
    document_number: '',
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    address: '',
    latitude: '',
    longitude: '',
    price_list: 'default',
    credit_days: '',
    credit_limit: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [docTypesRes, priceListsRes] = await Promise.all([
        axios.get(`${API}/document-types`),
        axios.get(`${API}/price-lists`)
      ]);
      list.reload();
      setDocumentTypes(docTypesRes.data);
      setPriceLists(priceListsRes.data);
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const { credit_days: creditDays, credit_limit: creditLimit, ...rest } = formData;
      const payload = {
        ...rest,
        latitude: formData.latitude ? parseFloat(formData.latitude) : null,
        longitude: formData.longitude ? parseFloat(formData.longitude) : null
      };
      // P2.30: solo el administrador asigna plazo y cupo (vacío = plazo por defecto / sin cupo).
      // Los demás no los envían: el servidor lo rechazaría.
      if (isAdmin) {
        payload.credit_days = creditDays === '' ? null : Number(creditDays);
        payload.credit_limit = creditLimit === '' ? null : Number(creditLimit);
        if ((payload.credit_days !== null && (!Number.isInteger(payload.credit_days) || payload.credit_days < 0))
            || (payload.credit_limit !== null && (Number.isNaN(payload.credit_limit) || payload.credit_limit < 0))) {
          toast.error('El plazo debe ser un número entero de días (0 o más) y el cupo un valor de 0 o más.');
          setIsSubmitting(false);
          return;
        }
      }

      if (editMode) {
        // P1.15: tipo + número identifican al cliente (CC 123 y NIT 123 son distintos).
        await axios.put(`${API}/clients/${encodeURIComponent(currentClient.document_number)}`, payload, {
          params: { document_type: currentClient.document_type },
        });
        toast.success('Cliente actualizado');
      } else {
        await axios.post(`${API}/clients`, payload);
        toast.success('Cliente creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar cliente'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenDialog = (client = null) => {
    if (client) {
      setEditMode(true);
      setCurrentClient(client);
      setFormData({
        document_type: client.document_type,
        document_number: client.document_number,
        first_name: client.first_name,
        last_name: client.last_name,
        phone: client.phone || '',
        email: client.email || '',
        address: client.address || '',
        latitude: client.latitude?.toString() || '',
        longitude: client.longitude?.toString() || '',
        price_list: client.price_list,
        credit_days: client.credit_days ?? '',
        credit_limit: client.credit_limit ? String(client.credit_limit) : ''
      });
    } else {
      setEditMode(false);
      setCurrentClient(null);
      setFormData({
        document_type: '',
        document_number: '',
        first_name: '',
        last_name: '',
        phone: '',
        email: '',
        address: '',
        latitude: '',
        longitude: '',
        price_list: 'default',
        credit_days: '',
        credit_limit: ''
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentClient(null);
  };

  const handleDelete = async (client) => {
    if (!window.confirm(`¿Estás seguro de eliminar al cliente ${client.first_name} ${client.last_name} (${client.document_type} ${client.document_number})?`)) return;
    try {
      await axios.delete(`${API}/clients/${encodeURIComponent(client.document_number)}`, {
        params: { document_type: client.document_type },
      });
      toast.success('Cliente eliminado');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar cliente'));
    }
  };

  const filteredClients = list.items;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="clients-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Clientes</h1>
          <p className="text-muted-foreground mt-2">Gestiona tu base de clientes</p>
        </div>
        {canCreate('clients') && (
          <Button onClick={() => handleOpenDialog()} data-testid="create-client-button">
            <Plus className="h-4 w-4 mr-2" />
            Nuevo Cliente
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="client-dialog">
            <DialogHeader>
              <DialogTitle>{editMode ? 'Editar Cliente' : 'Nuevo Cliente'}</DialogTitle>
              <DialogDescription>
                {editMode ? 'Modifica los datos del cliente' : 'Registra un nuevo cliente'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="document_type">Tipo de Documento *</Label>
                    <Select
                      value={formData.document_type}
                      onValueChange={(value) => setFormData({ ...formData, document_type: value })}
                      required
                      disabled={editMode}
                    >
                      <SelectTrigger data-testid="client-document-type-select">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent>
                        {documentTypes.map((dt) => (
                          <SelectItem key={dt.code} value={dt.code}>
                            {dt.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="document_number">Número de Documento *</Label>
                    <Input
                      id="document_number"
                      value={formData.document_number}
                      onChange={(e) => setFormData({ ...formData, document_number: e.target.value })}
                      required
                      disabled={editMode}
                      data-testid="client-document-number-input"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">Nombres *</Label>
                    <Input
                      id="first_name"
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                      required
                      data-testid="client-first-name-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="last_name">Apellidos *</Label>
                    <Input
                      id="last_name"
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                      required
                      data-testid="client-last-name-input"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Teléfono</Label>
                    <Input
                      id="phone"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      data-testid="client-phone-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      data-testid="client-email-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="address">Dirección</Label>
                  <Input
                    id="address"
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    data-testid="client-address-input"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="latitude">Latitud</Label>
                    <Input
                      id="latitude"
                      type="number"
                      step="any"
                      value={formData.latitude}
                      onChange={(e) => setFormData({ ...formData, latitude: e.target.value })}
                      data-testid="client-latitude-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="longitude">Longitud</Label>
                    <Input
                      id="longitude"
                      type="number"
                      step="any"
                      value={formData.longitude}
                      onChange={(e) => setFormData({ ...formData, longitude: e.target.value })}
                      data-testid="client-longitude-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="price_list">Lista de Precios *</Label>
                  <Select
                    value={formData.price_list}
                    onValueChange={(value) => setFormData({ ...formData, price_list: value })}
                  >
                    <SelectTrigger data-testid="client-price-list-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {priceLists.filter(pl => pl.is_active).map((pl) => (
                        <SelectItem key={pl.name} value={pl.name}>
                          {pl.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="credit_days">Plazo de crédito (días)</Label>
                    <Input id="credit_days" type="number" min="0" step="1" placeholder="Por defecto" disabled={!isAdmin}
                           value={formData.credit_days}
                           onChange={(e) => setFormData({ ...formData, credit_days: e.target.value })} data-testid="client-credit-days-input" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="credit_limit">Cupo de crédito</Label>
                    <Input id="credit_limit" type="number" min="0" step="1" placeholder="Sin límite" disabled={!isAdmin}
                           value={formData.credit_limit}
                           onChange={(e) => setFormData({ ...formData, credit_limit: e.target.value })} data-testid="client-credit-limit-input" />
                  </div>
                  <p className="col-span-2 text-xs text-muted-foreground -mt-2">
                    {isAdmin
                      ? 'Vacío: usa el plazo de Config. Sistema y no tiene límite de cupo. Una venta a crédito que supere el cupo se rechaza.'
                      : 'Solo un administrador puede asignar el plazo y el cupo de crédito.'}
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSubmitting} data-testid="save-client-button">
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
            placeholder="Buscar por documento o nombre..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-clients-input"
          />
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Documento</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Teléfono</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Lista Precios</TableHead>
              <TableHead>Crédito</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredClients.map((client, index) => (
              <TableRow key={client.document_number} data-testid={`client-row-${index}`}>
                <TableCell className="font-mono">{client.document_number}</TableCell>
                <TableCell>{`${client.first_name} ${client.last_name}`}</TableCell>
                <TableCell>{client.phone || '-'}</TableCell>
                <TableCell>{client.email || '-'}</TableCell>
                <TableCell>{client.price_list}</TableCell>
                <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                  {client.credit_days != null ? `${client.credit_days} días` : 'Plazo por defecto'}
                  {client.credit_limit ? ` · cupo ${money(client.credit_limit)}` : ''}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    {client.latitude && client.longitude && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => window.open(`https://maps.google.com/?q=${client.latitude},${client.longitude}`, '_blank')}
                        data-testid={`view-map-${index}`}
                      >
                        <MapPin className="h-4 w-4" />
                      </Button>
                    )}
                    {canUpdate('clients') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenDialog(client)}
                        data-testid={`edit-client-${index}`}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                    )}
                    {canDelete('clients') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(client)}
                        data-testid={`delete-client-${index}`}
                      >
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

      {filteredClients.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-clients">
          No se encontraron clientes
        </div>
      )}
      <Pagination {...list.paginationProps} noun="cliente(s)" testId="clients-pagination" />
    </div>
  );
};

export default Clients;