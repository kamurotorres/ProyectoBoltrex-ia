import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext, API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';

const MIN_LENGTH = 8;

// Cambiar la contraseña propia (backlog P1.10). Se usa de dos formas:
//  - Obligatoria: el usuario tiene `must_change_password` (p. ej. el admin creado con
//    ADMIN_INITIAL_PASSWORD). El backend rechaza cualquier otra acción hasta que la cambie.
//  - Voluntaria: desde el botón "Contraseña" del menú lateral.
const ChangePassword = () => {
  const { user, logout, markPasswordChanged } = useContext(AuthContext);
  const navigate = useNavigate();
  const forced = Boolean(user?.must_change_password);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Validaciones locales con mensaje en pantalla; el backend vuelve a validarlo todo.
    if (newPassword.length < MIN_LENGTH) {
      toast.error(`La nueva contraseña debe tener al menos ${MIN_LENGTH} caracteres.`);
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('La confirmación no coincide con la nueva contraseña.');
      return;
    }
    if (newPassword === currentPassword) {
      toast.error('La nueva contraseña debe ser distinta de la actual.');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/change-password`, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success(response.data?.message || 'Contraseña actualizada correctamente.');
      markPasswordChanged();
      navigate('/', { replace: true });
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cambiar la contraseña'));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md" data-testid="change-password-card">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold tracking-tight">Cambiar contraseña</CardTitle>
          <CardDescription className="text-base">
            {forced
              ? 'Por seguridad debes cambiar tu contraseña antes de continuar. Hasta que lo hagas no podrás usar el sistema.'
              : 'Escribe tu contraseña actual y la nueva.'}
          </CardDescription>
          <p className="text-xs text-muted-foreground font-mono">{user?.email}</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Contraseña actual</Label>
              <Input
                id="currentPassword"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                data-testid="current-password-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">Nueva contraseña</Label>
              <Input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                data-testid="new-password-input"
              />
              <p className="text-xs text-muted-foreground">Mínimo {MIN_LENGTH} caracteres. No uses contraseñas comunes como admin123.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirmar nueva contraseña</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                data-testid="confirm-password-input"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="change-password-submit">
              {loading ? 'Guardando...' : 'Cambiar contraseña'}
            </Button>
            {forced ? (
              <Button type="button" variant="ghost" className="w-full" onClick={handleLogout} data-testid="change-password-logout">
                Cerrar sesión
              </Button>
            ) : (
              <Button type="button" variant="ghost" className="w-full" onClick={() => navigate(-1)} data-testid="change-password-cancel">
                Cancelar
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChangePassword;
