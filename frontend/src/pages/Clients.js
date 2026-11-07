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
import { Plus, Search, Edit, MapPin, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { money } from '@/lib/format';
import { API, api } from '@/api/client';
import { useConfirm } from '@/components/ConfirmDialog';
import { useZodForm } from '@/hooks/useZodForm';
import { SelectField, TextField } from '@/components/form/Field';
import { clientSchema } from '@/lib/schemas';

const EMPTY = {
  document_type: '', document_number: '', first_name: '', last_name: '', phone: '', email: '', address: '',
  latitude: '', longitude: '', price_list: 'default', credit_days: '', credit_limit: '',
};

const Clients = () => {
  const { canCreate, canUpdate, canDelete, isAdmin } = usePermissions();
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
  // P1.18: clientes paginados y buscados en el servidor.
  const list = usePaginatedList(`${API}/clients`, { errorMessage: 'Error al cargar clientes' });
  const [documentTypes, setDocumentTypes] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentClient, setCurrentClient] = useState(null);
  // fase 6: formulario con react-hook-form + zod (errores debajo de cada campo).
  const form = useZodForm(clientSchema, EMPTY);
  const isSubmitting = form.submitting;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [docTypesRes, priceListsRes] = await Promise.all([
        api.get(`/document-types`),
        api.get(`/price-lists`)
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

  const handleSubmit = form.submit(async (formData) => {
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
        // fase 6: el plazo (entero 0–3650) y el cupo (≥ 0) ya los validó el esquema, con el error en su campo.
      }

      if (editMode) {
        // P1.15: tipo + número identifican al cliente (CC 123 y NIT 123 son distintos).
        await api.put(`/clients/${encodeURIComponent(currentClient.document_number)}`, payload, {
          params: { document_type: currentClient.document_type },
        });
        toast.success('Cliente actualizado');
      } else {
        await api.post(`/clients`, payload);
        toast.success('Cliente creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar cliente'));
    }
  });

  const handleOpenDialog = (client = null) => {
    if (client) {
      setEditMode(true);
      setCurrentClient(client);
      form.reset({
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
      form.reset(EMPTY);
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentClient(null);
  };

  const handleDelete = async (client) => {
    if (!(await confirm(`¿Estás seguro de eliminar al cliente ${client.first_name} ${client.last_name} (${client.document_type} ${client.document_number})?`, { confirmLabel: 'Eliminar', destructive: true }))) return;
    try {
      await api.delete(`/clients/${encodeURIComponent(client.document_number)}`, {
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
            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <SelectField form={form} name="document_type" label="Tipo de Documento *" placeholder="Seleccionar"
                               disabled={editMode} triggerTestId="client-document-type-select"
                               options={documentTypes.map((dt) => ({ value: dt.code, label: dt.name }))} />
                  <TextField form={form} name="document_number" label="Número de Documento *" disabled={editMode}
                             data-testid="client-document-number-input" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <TextField form={form} name="first_name" label="Nombres *" data-testid="client-first-name-input" />
                  <TextField form={form} name="last_name" label="Apellidos *" data-testid="client-last-name-input" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <TextField form={form} name="phone" label="Teléfono" data-testid="client-phone-input" />
                  <TextField form={form} name="email" label="Email" type="email" data-testid="client-email-input" />
                </div>

                <TextField form={form} name="address" label="Dirección" data-testid="client-address-input" />

                <div className="grid grid-cols-2 gap-4">
                  <TextField form={form} name="latitude" label="Latitud" type="number" step="any" data-testid="client-latitude-input" />
                  <TextField form={form} name="longitude" label="Longitud" type="number" step="any" data-testid="client-longitude-input" />
                </div>

                <SelectField form={form} name="price_list" label="Lista de Precios *" triggerTestId="client-price-list-select"
                             options={priceLists.filter((pl) => pl.is_active).map((pl) => ({ value: pl.name, label: pl.name }))} />

                <div className="grid grid-cols-2 gap-4">
                  <TextField form={form} name="credit_days" label="Plazo de crédito (días)" type="number" min="0" step="1"
                             placeholder="Por defecto" disabled={!isAdmin} data-testid="client-credit-days-input" />
                  <TextField form={form} name="credit_limit" label="Cupo de crédito" type="number" min="0" step="1"
                             placeholder="Sin límite" disabled={!isAdmin} data-testid="client-credit-limit-input" />
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