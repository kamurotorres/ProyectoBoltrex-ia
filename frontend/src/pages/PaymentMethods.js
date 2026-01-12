import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  CreditCard, 
  Plus, 
  Pencil, 
  Trash2, 
  Check, 
  X,
  ToggleLeft,
  ToggleRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { usePermissions } from '@/hooks/usePermissions';
import { API } from '@/App';

const PaymentMethods = () => {
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editingMethod, setEditingMethod] = useState(null);
  const [methodToDelete, setMethodToDelete] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true
  });

  const { canCreate, canUpdate, canDelete } = usePermissions();
  const moduleSlug = 'payment-methods';

  useEffect(() => {
    fetchPaymentMethods();
  }, []);

  const fetchPaymentMethods = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/payment-methods`);
      setPaymentMethods(response.data);
    } catch (error) {
      toast.error('Error al cargar las formas de pago');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreate = () => {
    setEditingMethod(null);
    setFormData({ name: '', description: '', is_active: true });
    setShowDialog(true);
  };

  const handleOpenEdit = (method) => {
    setEditingMethod(method);
    setFormData({
      name: method.name,
      description: method.description || '',
      is_active: method.is_active
    });
    setShowDialog(true);
  };

  const handleOpenDelete = (method) => {
    setMethodToDelete(method);
    setShowDeleteDialog(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      toast.error('El nombre es requerido');
      return;
    }

    try {
      if (editingMethod) {
        await axios.put(`${API}/payment-methods/${editingMethod.name}`, formData);
        toast.success('Forma de pago actualizada');
      } else {
        await axios.post(`${API}/payment-methods`, formData);
        toast.success('Forma de pago creada');
      }
      setShowDialog(false);
      fetchPaymentMethods();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar');
    }
  };

  const handleDelete = async () => {
    try {
      await axios.delete(`${API}/payment-methods/${methodToDelete.name}`);
      toast.success('Forma de pago eliminada');
      setShowDeleteDialog(false);
      setMethodToDelete(null);
      fetchPaymentMethods();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    }
  };

  const handleToggleStatus = async (method) => {
    try {
      await axios.put(`${API}/payment-methods/${method.name}`, {
        is_active: !method.is_active
      });
      toast.success(`Forma de pago ${!method.is_active ? 'activada' : 'desactivada'}`);
      fetchPaymentMethods();
    } catch (error) {
      toast.error('Error al cambiar el estado');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="payment-methods-loading">
        <div className="text-muted-foreground">Cargando...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="payment-methods-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" data-testid="payment-methods-title">
            <CreditCard className="h-6 w-6" />
            Formas de Pago
          </h1>
          <p className="text-muted-foreground mt-1">
            Administra las formas de pago disponibles para ventas y abonos
          </p>
        </div>
        {canCreate(moduleSlug) && (
          <Button onClick={handleOpenCreate} data-testid="create-payment-method-btn">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Forma de Pago
          </Button>
        )}
      </div>

      {/* Payment Methods Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {paymentMethods.map((method) => (
          <div
            key={method.name}
            className={`bg-card border rounded-lg p-4 transition-all ${
              method.is_active ? 'border-border' : 'border-border/50 opacity-60'
            }`}
            data-testid={`payment-method-${method.name}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{method.name}</h3>
                  {method.is_active ? (
                    <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded-full">
                      Activo
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full">
                      Inactivo
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {method.description || 'Sin descripción'}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
              {canUpdate(moduleSlug) && (
                <button
                  onClick={() => handleToggleStatus(method)}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  data-testid={`toggle-status-${method.name}`}
                >
                  {method.is_active ? (
                    <>
                      <ToggleRight className="h-4 w-4 text-green-500" />
                      <span>Desactivar</span>
                    </>
                  ) : (
                    <>
                      <ToggleLeft className="h-4 w-4" />
                      <span>Activar</span>
                    </>
                  )}
                </button>
              )}
              
              <div className="flex items-center gap-2">
                {canUpdate(moduleSlug) && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleOpenEdit(method)}
                    data-testid={`edit-payment-method-${method.name}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                {canDelete(moduleSlug) && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleOpenDelete(method)}
                    data-testid={`delete-payment-method-${method.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {paymentMethods.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No hay formas de pago registradas
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent data-testid="payment-method-dialog">
          <DialogHeader>
            <DialogTitle>
              {editingMethod ? 'Editar Forma de Pago' : 'Nueva Forma de Pago'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nombre *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Ej: Efectivo, Tarjeta de Crédito"
                disabled={!!editingMethod}
                data-testid="input-payment-method-name"
              />
              {editingMethod && (
                <p className="text-xs text-muted-foreground">
                  El nombre no se puede modificar
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Descripción</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Descripción opcional"
                rows={2}
                data-testid="input-payment-method-description"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">Estado</Label>
              <div className="flex items-center gap-2">
                <span className={`text-sm ${!formData.is_active ? 'text-foreground' : 'text-muted-foreground'}`}>
                  Inactivo
                </span>
                <Switch
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  data-testid="switch-payment-method-status"
                />
                <span className={`text-sm ${formData.is_active ? 'text-foreground' : 'text-muted-foreground'}`}>
                  Activo
                </span>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                Cancelar
              </Button>
              <Button type="submit" data-testid="save-payment-method-btn">
                {editingMethod ? 'Guardar Cambios' : 'Crear'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent data-testid="delete-payment-method-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar forma de pago?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. Se eliminará permanentemente la forma de pago
              <strong> "{methodToDelete?.name}"</strong>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              data-testid="confirm-delete-payment-method"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PaymentMethods;
