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
import { Plus, Search, Edit, MapPin } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const Clients = () => {
  const { canCreate, canUpdate } = usePermissions();
  const [clients, setClients] = useState([]);
  const [documentTypes, setDocumentTypes] = useState([]);
  const [priceLists, setPriceLists] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
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
    price_list: 'default'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [clientsRes, docTypesRes, priceListsRes] = await Promise.all([
        axios.get(`${API}/clients`),
        axios.get(`${API}/document-types`),
        axios.get(`${API}/price-lists`)
      ]);
      setClients(clientsRes.data);
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
    try {
      const payload = {
        ...formData,
        latitude: formData.latitude ? parseFloat(formData.latitude) : null,
        longitude: formData.longitude ? parseFloat(formData.longitude) : null
      };

      if (editMode) {
        await axios.put(`${API}/clients/${currentClient.document_number}`, payload);
        toast.success('Cliente actualizado');
      } else {
        await axios.post(`${API}/clients`, payload);
        toast.success('Cliente creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar cliente');
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
        price_list: client.price_list
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
        price_list: 'default'
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentClient(null);
  };

  const filteredClients = clients.filter(c =>
    search === '' ||
    c.document_number.toLowerCase().includes(search.toLowerCase()) ||
    c.first_name.toLowerCase().includes(search.toLowerCase()) ||
    c.last_name.toLowerCase().includes(search.toLowerCase())
  );

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
                      <SelectItem value="default">Default</SelectItem>
                      {priceLists.map((pl) => (
                        <SelectItem key={pl.name} value={pl.name}>
                          {pl.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" data-testid="save-client-button">
                  {editMode ? 'Actualizar' : 'Crear'}
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
            value={search}
            onChange={(e) => setSearch(e.target.value)}
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
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {filteredClients.length === 0 && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-clients">
          No se encontraron clientes
        </div>
      )}
    </div>
  );
};

export default Clients;