import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Settings, 
  Save, 
  Building2,
  Phone,
  Mail,
  MapPin,
  Hash,
  Ruler,
  MessageSquare,
  RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { API } from '@/App';
import { usePermissions } from '@/hooks/usePermissions';

const TicketConfig = () => {
  const { canUpdate } = usePermissions();
  const [config, setConfig] = useState({
    company_name: '',
    nit: '',
    phone: '',
    email: '',
    address: '',
    ticket_width: 80,
    footer_message: '¡Gracias por su compra!'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/ticket-config`);
      setConfig(response.data);
    } catch (error) {
      toast.error('Error al cargar la configuración');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!config.company_name.trim()) {
      toast.error('El nombre de la empresa es requerido');
      return;
    }
    
    try {
      setSaving(true);
      await axios.put(`${API}/ticket-config`, config);
      toast.success('Configuración guardada exitosamente');
    } catch (error) {
      toast.error('Error al guardar la configuración');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="ticket-config-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl" data-testid="ticket-config-page">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" data-testid="ticket-config-title">
          <Settings className="h-6 w-6" />
          Configuración de Tickets
        </h1>
        <p className="text-muted-foreground mt-1">
          Configure la información que aparecerá en los tickets de venta
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Company Info Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Building2 className="h-5 w-5" />
              Información de la Empresa
            </CardTitle>
            <CardDescription>
              Estos datos aparecerán en el encabezado de cada ticket
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="company_name" className="flex items-center gap-1">
                  <Building2 className="h-4 w-4" />
                  Nombre de la Empresa *
                </Label>
                <Input
                  id="company_name"
                  value={config.company_name}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                  placeholder="Mi Empresa S.A.S"
                  required
                  data-testid="input-company-name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nit" className="flex items-center gap-1">
                  <Hash className="h-4 w-4" />
                  NIT / Identificación Fiscal
                </Label>
                <Input
                  id="nit"
                  value={config.nit}
                  onChange={(e) => handleChange('nit', e.target.value)}
                  placeholder="900.123.456-7"
                  data-testid="input-nit"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="phone" className="flex items-center gap-1">
                  <Phone className="h-4 w-4" />
                  Teléfono
                </Label>
                <Input
                  id="phone"
                  value={config.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                  placeholder="+57 300 123 4567"
                  data-testid="input-phone"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email" className="flex items-center gap-1">
                  <Mail className="h-4 w-4" />
                  Correo Electrónico
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={config.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  placeholder="contacto@empresa.com"
                  data-testid="input-email"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="address" className="flex items-center gap-1">
                <MapPin className="h-4 w-4" />
                Dirección
              </Label>
              <Textarea
                id="address"
                value={config.address}
                onChange={(e) => handleChange('address', e.target.value)}
                placeholder="Calle 123 #45-67, Ciudad, País"
                rows={2}
                data-testid="input-address"
              />
            </div>
          </CardContent>
        </Card>

        {/* Ticket Format Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Ruler className="h-5 w-5" />
              Formato del Ticket
            </CardTitle>
            <CardDescription>
              Seleccione el tamaño del papel para su impresora térmica
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ticket_width" className="flex items-center gap-1">
                <Ruler className="h-4 w-4" />
                Ancho del Papel
              </Label>
              <Select
                value={String(config.ticket_width)}
                onValueChange={(value) => handleChange('ticket_width', Number(value))}
              >
                <SelectTrigger data-testid="select-ticket-width">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="58">58mm - Estándar pequeño</SelectItem>
                  <SelectItem value="80">80mm - Estándar grande</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                Seleccione según el tipo de impresora térmica que utiliza
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="footer_message" className="flex items-center gap-1">
                <MessageSquare className="h-4 w-4" />
                Mensaje de Pie de Página
              </Label>
              <Input
                id="footer_message"
                value={config.footer_message}
                onChange={(e) => handleChange('footer_message', e.target.value)}
                placeholder="¡Gracias por su compra!"
                data-testid="input-footer-message"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Este mensaje aparecerá al final de cada ticket
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Preview Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Vista Previa del Encabezado</CardTitle>
            <CardDescription>
              Así se verá el encabezado de sus tickets
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div 
              className="bg-white text-black p-4 rounded-lg font-mono text-sm text-center border"
              style={{ maxWidth: config.ticket_width === 58 ? '220px' : '300px' }}
              data-testid="ticket-preview"
            >
              <p className="font-bold text-base">{config.company_name || 'NOMBRE EMPRESA'}</p>
              {config.nit && <p className="text-xs">NIT: {config.nit}</p>}
              {config.phone && <p className="text-xs">Tel: {config.phone}</p>}
              {config.email && <p className="text-xs">{config.email}</p>}
              {config.address && <p className="text-xs">{config.address}</p>}
              <div className="border-t border-dashed border-gray-400 my-2" />
              <p className="text-xs text-gray-500 italic">{config.footer_message}</p>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button 
            type="button" 
            variant="outline" 
            onClick={fetchConfig}
            disabled={saving}
            data-testid="reset-btn"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Restablecer
          </Button>
          <Button type="submit" disabled={saving} data-testid="save-config-btn">
            {saving ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Guardar Configuración
          </Button>
        </div>
      </form>
    </div>
  );
};

export default TicketConfig;
