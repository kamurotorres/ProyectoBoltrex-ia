import React, { useState, useContext } from 'react';
import axios from 'axios';
import { API, AuthContext } from '@/App';
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, RotateCcw, ShieldAlert, Package, FolderOpen, Users, Truck, ShoppingBag, Receipt, Wallet, Warehouse, CreditCard, UserCog } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const affectedModules = [
  { icon: Package, label: 'Productos' },
  { icon: FolderOpen, label: 'Categorías' },
  { icon: Users, label: 'Clientes' },
  { icon: Truck, label: 'Proveedores' },
  { icon: ShoppingBag, label: 'Compras' },
  { icon: RotateCcw, label: 'Devoluciones' },
  { icon: Receipt, label: 'Facturas' },
  { icon: Wallet, label: 'Fios (Créditos)' },
  { icon: Warehouse, label: 'Inventario' },
  { icon: CreditCard, label: 'Formas de Pago' },
  { icon: UserCog, label: 'Usuarios (excepto admin)' },
];

const FactoryReset = () => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { logout } = useContext(AuthContext);
  const navigate = useNavigate();

  const handleReset = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}/system/factory-reset`, { password });
      toast.success('Sistema restablecido a valores de fábrica');
      setDialogOpen(false);
      setPassword('');
      logout();
      navigate('/login');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al restablecer el sistema');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setDialogOpen(false);
    setPassword('');
  };

  return (
    <div data-testid="factory-reset-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Configuración del Sistema</h1>
        <p className="text-muted-foreground mt-2">Administración y mantenimiento del sistema</p>
      </div>

      <Card className="border-destructive/30">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-destructive/10">
              <ShieldAlert className="h-6 w-6 text-destructive" />
            </div>
            <div>
              <CardTitle className="text-destructive">Zona de Peligro</CardTitle>
              <CardDescription>Acciones irreversibles del sistema</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 rounded-lg border border-destructive/20 bg-destructive/5">
            <div>
              <p className="font-medium">Restablecer a valores de fábrica</p>
              <p className="text-sm text-muted-foreground mt-1">
                Elimina todos los datos y restaura la configuración inicial del sistema.
              </p>
            </div>
            <Button
              variant="destructive"
              onClick={() => setDialogOpen(true)}
              data-testid="factory-reset-button"
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              Restablecer Sistema
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={handleClose}>
        <DialogContent className="max-w-lg" data-testid="factory-reset-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Restablecer a valores de fábrica
            </DialogTitle>
            <DialogDescription className="pt-2">
              <span className="block p-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive font-medium text-sm">
                ADVERTENCIA: Esta acción es irreversible. Se eliminarán permanentemente todos los datos del sistema y se restaurará la configuración inicial.
              </span>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <p className="text-sm font-medium mb-3">Se limpiarán los siguientes componentes:</p>
              <div className="grid grid-cols-2 gap-2">
                {affectedModules.map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-2 text-sm p-2 rounded-md bg-muted/50">
                    <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t">
              <Label htmlFor="confirm-password" className="text-sm font-medium">
                Ingrese su contraseña de Administrador para confirmar:
              </Label>
              <Input
                id="confirm-password"
                type="password"
                placeholder="Contraseña del administrador"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="factory-reset-password-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={handleClose} disabled={loading} data-testid="factory-reset-cancel">
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={handleReset}
              disabled={!password || loading}
              data-testid="factory-reset-confirm"
            >
              {loading ? (
                <RotateCcw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <AlertTriangle className="h-4 w-4 mr-2" />
              )}
              {loading ? 'Restableciendo...' : 'Confirmar Restablecimiento'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default FactoryReset;
