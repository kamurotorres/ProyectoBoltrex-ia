import React, { useState, useEffect } from 'react';
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
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/api/client';
import { useZodForm } from '@/hooks/useZodForm';
import { FieldError } from '@/components/form/Field';
import { ticketConfigSchema } from '@/lib/schemas';

const TicketConfig = () => {
  const { canUpdate } = usePermissions();
  // fase 6: formulario con react-hook-form + zod (errores debajo de cada campo); la vista previa usa los
  // valores que se van escribiendo.
  const form = useZodForm(ticketConfigSchema, {
    company_name: '',
    nit: '',
    phone: '',
    email: '',
    address: '',
    ticket_width: 80,
    footer_message: '¡Gracias por su compra!'
  });
  const config = form.watch();
  const [loading, setLoading] = useState(true);
  const saving = form.submitting;
  const errors = form.errors;
  const errorClass = (name) => (errors[name] ? 'border-destructive' : undefined);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/ticket-config`);
      form.reset(response.data);
    } catch (error) {
      toast.error('Error al cargar la configuración');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = form.submit(async (config) => {
    try {
      await api.put(`/ticket-config`, config);
      toast.success('Configuración guardada exitosamente');
    } catch (error) {
      toast.error('Error al guardar la configuración');
      console.error(error);
    }
  });

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

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {/* Sin permiso de editar, los campos quedan de solo lectura (P1.13). */}
        <fieldset disabled={!canUpdate('ticket-config')} className="space-y-6 disabled:opacity-90">
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
                  {...form.register('company_name')}
                  className={errorClass('company_name')}
                  placeholder="Mi Empresa S.A.S"
                  data-testid="input-company-name"
                />
                <FieldError error={errors.company_name} id="company_name-error" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nit" className="flex items-center gap-1">
                  <Hash className="h-4 w-4" />
                  NIT / Identificación Fiscal
                </Label>
                <Input
                  id="nit"
                  {...form.register('nit')}
                  className={errorClass('nit')}
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
                  {...form.register('phone')}
                  className={errorClass('phone')}
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
                  {...form.register('email')}
                  className={errorClass('email')}
                  placeholder="contacto@empresa.com"
                  data-testid="input-email"
                />
                <FieldError error={errors.email} id="email-error" />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="address" className="flex items-center gap-1">
                <MapPin className="h-4 w-4" />
                Dirección
              </Label>
              <Textarea
                id="address"
                {...form.register('address')}
                className={errorClass('address')}
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
                onValueChange={(value) => form.setValue('ticket_width', Number(value), { shouldValidate: form.formState.isSubmitted })}
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
              <FieldError error={errors.ticket_width} id="ticket_width-error" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="footer_message" className="flex items-center gap-1">
                <MessageSquare className="h-4 w-4" />
                Mensaje de Pie de Página
              </Label>
              <Input
                id="footer_message"
                {...form.register('footer_message')}
                className={errorClass('footer_message')}
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
              style={{ maxWidth: Number(config.ticket_width) === 58 ? '220px' : '300px' }}
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
        </fieldset>

        {/* Actions */}
        {canUpdate('ticket-config') && (
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
          {canUpdate('ticket-config') && (
            <Button type="submit" disabled={saving} data-testid="save-config-btn">
              {saving ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Guardar Configuración
            </Button>
          )}
        </div>
        )}
      </form>
    </div>
  );
};

export default TicketConfig;
