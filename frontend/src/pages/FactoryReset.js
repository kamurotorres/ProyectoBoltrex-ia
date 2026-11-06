import React, { useState, useContext, useEffect } from 'react';
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
import { Switch } from '@/components/ui/switch';
import { getErrorMessage } from '@/lib/utils';
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
  { icon: UserCog, label: 'Usuarios (excepto admin@boltrex.com y tu usuario)' },
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

  // P2.31: «Exigir caja abierta para vender» (activado = opción A; desactivado = opción B).
  const [requireCash, setRequireCash] = useState(null);
  const [savingCash, setSavingCash] = useState(false);
  useEffect(() => {
    axios.get(`${API}/cash/settings`).then((r) => setRequireCash(!!r.data.require_open_session))
      .catch((e) => toast.error(getErrorMessage(e, 'No se pudo leer la configuración de caja')));
  }, []);
  const toggleRequireCash = async (value) => {
    setSavingCash(true);
    try {
      const r = await axios.put(`${API}/cash/settings`, { require_open_session: value });
      setRequireCash(!!r.data.require_open_session);
      toast.success(value ? 'Ahora se exige caja abierta para vender.' : 'Ya no se exige caja abierta para vender.');
    } catch (e) {
      toast.error(getErrorMessage(e, 'No se pudo cambiar la configuración de caja'));
    } finally {
      setSavingCash(false);
    }
  };

  // P2.34: stock mínimo general (cada producto puede tener el suyo).
  const [invCfg, setInvCfg] = useState(null);
  const [lowInput, setLowInput] = useState('');
  const [savingInv, setSavingInv] = useState(false);
  useEffect(() => {
    axios.get(`${API}/inventory/settings`).then((r) => { setInvCfg(r.data); setLowInput(String(r.data.low_stock_threshold)); })
      .catch((e) => toast.error(getErrorMessage(e, 'No se pudo leer la configuración de inventario')));
  }, []);
  const saveInv = async () => {
    const n = Number(lowInput);
    if (lowInput === '' || !Number.isInteger(n) || n < 0) {
      toast.error('El stock mínimo general debe ser un número entero (0 o más).');
      return;
    }
    setSavingInv(true);
    try {
      const r = await axios.put(`${API}/inventory/settings`, { low_stock_threshold: n });
      setInvCfg(r.data);
      setLowInput(String(r.data.low_stock_threshold));
      toast.success('Stock mínimo general guardado.');
    } catch (e) {
      toast.error(getErrorMessage(e, 'No se pudo guardar el stock mínimo general'));
    } finally {
      setSavingInv(false);
    }
  };

  // P2.30: plazo de crédito por defecto y días para «Por vencer».
  const [creditCfg, setCreditCfg] = useState(null);
  const [creditForm, setCreditForm] = useState({ default_term_days: '', due_soon_days: '' });
  const [savingCredit, setSavingCredit] = useState(false);
  useEffect(() => {
    axios.get(`${API}/credit/settings`).then((r) => {
      setCreditCfg(r.data);
      setCreditForm({ default_term_days: String(r.data.default_term_days), due_soon_days: String(r.data.due_soon_days) });
    }).catch((e) => toast.error(getErrorMessage(e, 'No se pudo leer la configuración de crédito')));
  }, []);
  const creditDirty = creditCfg && (String(creditCfg.default_term_days) !== creditForm.default_term_days
    || String(creditCfg.due_soon_days) !== creditForm.due_soon_days);
  const saveCredit = async () => {
    const term = Number(creditForm.default_term_days);
    const soon = Number(creditForm.due_soon_days);
    if (creditForm.default_term_days === '' || !Number.isInteger(term) || term < 0) {
      toast.error('El plazo de crédito debe ser un número entero de días (0 o más).');
      return;
    }
    if (creditForm.due_soon_days === '' || !Number.isInteger(soon) || soon < 0) {
      toast.error('Los días para «Por vencer» deben ser un número entero (0 o más).');
      return;
    }
    setSavingCredit(true);
    try {
      const r = await axios.put(`${API}/credit/settings`, { default_term_days: term, due_soon_days: soon });
      setCreditCfg(r.data);
      setCreditForm({ default_term_days: String(r.data.default_term_days), due_soon_days: String(r.data.due_soon_days) });
      toast.success('Configuración de crédito guardada. Aplica a las nuevas ventas a crédito.');
    } catch (e) {
      toast.error(getErrorMessage(e, 'No se pudo guardar la configuración de crédito'));
    } finally {
      setSavingCredit(false);
    }
  };

  return (
    <div data-testid="factory-reset-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Configuración del Sistema</h1>
        <p className="text-muted-foreground mt-2">Administración y mantenimiento del sistema</p>
      </div>

      <Card className="mb-6" data-testid="cash-settings-card">
        <CardHeader>
          <CardTitle className="text-lg">Caja</CardTitle>
          <CardDescription>Control de caja por cajero (apertura, arqueo y cierre).</CardDescription>
        </CardHeader>
        <CardContent>
          <label className="flex items-start gap-3">
            <Switch checked={!!requireCash} disabled={requireCash === null || savingCash} onCheckedChange={toggleRequireCash} data-testid="require-cash-switch" />
            <span>
              <span className="font-medium">Exigir caja abierta para vender</span>
              <span className="block text-sm text-muted-foreground">
                {requireCash
                  ? 'Activado: nadie puede vender (ni a crédito), recibir abonos ni devolver efectivo sin tener su caja abierta.'
                  : 'Desactivado: se vende sin caja abierta; esos movimientos se suman a la próxima caja que abra el cajero.'}
              </span>
            </span>
          </label>
        </CardContent>
      </Card>

      <Card className="mb-6" data-testid="inventory-settings-card">
        <CardHeader>
          <CardTitle className="text-lg">Inventario</CardTitle>
          <CardDescription>
            Cuándo un producto está en «bajo stock» (alertas, Dashboard, Inventario y reportes). Cada producto puede tener su propio
            stock mínimo en Productos, que manda sobre este.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 max-w-xs">
            <Label htmlFor="low-stock">Stock mínimo general (unidades)</Label>
            <Input id="low-stock" type="number" min="0" step="1" value={lowInput} disabled={!invCfg}
                   onChange={(e) => setLowInput(e.target.value)} data-testid="low-stock-input" />
            <p className="text-xs text-muted-foreground">Alerta cuando quedan menos unidades que este número.</p>
          </div>
          <Button className="mt-4" onClick={saveInv} disabled={!invCfg || savingInv || String(invCfg.low_stock_threshold) === lowInput}
                  data-testid="low-stock-save-button">
            {savingInv ? 'Guardando…' : 'Guardar'}
          </Button>
        </CardContent>
      </Card>

      <Card className="mb-6" data-testid="credit-settings-card">
        <CardHeader>
          <CardTitle className="text-lg">Crédito (Fios)</CardTitle>
          <CardDescription>
            Plazo para pagar las ventas a crédito y aviso de facturas por vencer. Cada cliente puede tener su propio plazo y
            cupo (en Clientes), y en el POS se puede cambiar la fecha de una venta.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 max-w-xl">
            <div className="space-y-1">
              <Label htmlFor="credit-term">Plazo de crédito por defecto (días)</Label>
              <Input id="credit-term" type="number" min="0" step="1" value={creditForm.default_term_days} disabled={!creditCfg}
                     onChange={(e) => setCreditForm({ ...creditForm, default_term_days: e.target.value })} data-testid="credit-term-input" />
              <p className="text-xs text-muted-foreground">Vence ese número de días después de la venta (al final del día).</p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="credit-soon">Avisar «Por vencer» con (días)</Label>
              <Input id="credit-soon" type="number" min="0" step="1" value={creditForm.due_soon_days} disabled={!creditCfg}
                     onChange={(e) => setCreditForm({ ...creditForm, due_soon_days: e.target.value })} data-testid="credit-soon-input" />
              <p className="text-xs text-muted-foreground">Facturas que vencen hoy o en los próximos días indicados.</p>
            </div>
          </div>
          <Button className="mt-4" onClick={saveCredit} disabled={!creditDirty || savingCredit} data-testid="credit-save-button">
            {savingCredit ? 'Guardando…' : 'Guardar'}
          </Button>
        </CardContent>
      </Card>

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
