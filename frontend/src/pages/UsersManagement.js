import React, { useState, useEffect, useContext } from 'react';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Search, Edit, UserX, UserCheck, Shield, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { Badge } from '@/components/ui/badge';
import { usePermissions } from '@/hooks/usePermissions';
import { API, api } from '@/api/client';
import { AuthContext } from '@/auth/AuthProvider';
import { useZodForm } from '@/hooks/useZodForm';
import { TextField } from '@/components/form/Field';
import { userCreateSchema, userEditSchema } from '@/lib/schemas';

const EMPTY = { email: '', password: '', first_name: '', last_name: '', phone: '', is_active: true };

const UsersManagement = () => {
  const { canCreate, canUpdate } = usePermissions();
  const { user: loggedUser } = useContext(AuthContext);
  // P1.18: usuarios paginados y buscados en el servidor.
  const list = usePaginatedList(`${API}/rbac/users`, { errorMessage: 'Error al cargar usuarios' });
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAssigning, setIsAssigning] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [roleDialogOpen, setRoleDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [selectedUserRoles, setSelectedUserRoles] = useState([]);
  // fase 6: formulario con react-hook-form + zod (errores debajo de cada campo). Al editar, la contraseña es opcional.
  const form = useZodForm(editMode ? userEditSchema : userCreateSchema, EMPTY);
  const isSubmitting = form.submitting;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [rolesRes] = await Promise.all([
        api.get(`/rbac/roles`)
      ]);
      list.reload();
      setRoles(rolesRes.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al cargar datos'));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = form.submit(async (formData) => {
    try {
      if (editMode) {
        await api.put(`/rbac/users/${currentUser.email}`, formData);
        toast.success('Usuario actualizado');
      } else {
        await api.post(`/rbac/users`, formData);
        toast.success('Usuario creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al guardar usuario'));
    }
  });

  const handleOpenDialog = (user = null) => {
    if (user) {
      setEditMode(true);
      setCurrentUser(user);
      form.reset({
        email: user.email,
        password: '',
        first_name: user.first_name,
        last_name: user.last_name,
        phone: user.phone || '',
        is_active: user.is_active
      });
    } else {
      setEditMode(false);
      setCurrentUser(null);
      form.reset(EMPTY);
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditMode(false);
    setCurrentUser(null);
  };

  const handleToggleActive = async (email, isActive) => {
    try {
      await api.put(`/rbac/users/${email}`, { is_active: !isActive });
      toast.success(isActive ? 'Usuario desactivado' : 'Usuario activado');
      fetchData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al cambiar estado del usuario'));
    }
  };

  const handleOpenRoleDialog = (user) => {
    setCurrentUser(user);
    setSelectedUserRoles(user.roles || []);
    setRoleDialogOpen(true);
  };

  const handleAssignRoles = async () => {
    if (isAssigning) return;
    setIsAssigning(true);
    try {
      await api.post(`/rbac/users/${currentUser.email}/roles`, selectedUserRoles);
      toast.success('Roles asignados correctamente');
      fetchData();
      setRoleDialogOpen(false);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al asignar roles'));
    } finally {
      setIsAssigning(false);
    }
  };

  const handleToggleRole = (roleName) => {
    if (selectedUserRoles.includes(roleName)) {
      setSelectedUserRoles(selectedUserRoles.filter(r => r !== roleName));
    } else {
      setSelectedUserRoles([...selectedUserRoles, roleName]);
    }
  };

  const filteredUsers = list.items;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="users-management-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Gestión de Usuarios</h1>
          <p className="text-muted-foreground mt-2">Administra usuarios y sus accesos</p>
        </div>
        {canCreate('users') && (
          <Button onClick={() => handleOpenDialog()} data-testid="create-user-button">
            <Plus className="h-4 w-4 mr-2" />
            Nuevo Usuario
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent data-testid="user-dialog">
            <DialogHeader>
              <DialogTitle>{editMode ? 'Editar Usuario' : 'Nuevo Usuario'}</DialogTitle>
              <DialogDescription>
                {editMode ? 'Modifica los datos del usuario' : 'Crea un nuevo usuario en el sistema'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <TextField form={form} name="first_name" label="Nombres *" data-testid="user-first-name-input" />
                  <TextField form={form} name="last_name" label="Apellidos *" data-testid="user-last-name-input" />
                </div>

                {/* En edición el correo no se cambia (igual que antes): solo se muestra. */}
                {editMode ? (
                  <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input id="email" type="email" value={currentUser?.email || ''} disabled data-testid="user-email-input" />
                  </div>
                ) : (
                  <TextField form={form} name="email" label="Email *" type="email" data-testid="user-email-input" />
                )}

                <TextField form={form} name="password" type="password" autoComplete="new-password"
                           label={editMode ? 'Nueva Contraseña (opcional)' : 'Contraseña *'}
                           hint="Mínimo 8 caracteres; no se aceptan contraseñas obvias." data-testid="user-password-input" />

                <TextField form={form} name="phone" label="Teléfono" data-testid="user-phone-input" />

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    {...form.register('is_active')}
                    data-testid="user-active-checkbox"
                  />
                  <Label htmlFor="is_active">Usuario Activo</Label>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSubmitting} data-testid="save-user-button">
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
            placeholder="Buscar usuarios..."
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-users-input"
          />
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Teléfono</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredUsers.map((user, index) => (
              <TableRow key={user.email} data-testid={`user-row-${index}`}>
                <TableCell className="font-semibold">{`${user.first_name} ${user.last_name}`}</TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.phone || '-'}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {user.roles && user.roles.length > 0 ? (
                      user.roles.map(role => (
                        <Badge key={role} variant="secondary">{role}</Badge>
                      ))
                    ) : (
                      <span className="text-xs text-muted-foreground">Sin roles</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {user.is_active ? (
                    <Badge className="bg-chart-1/20 text-chart-1">Activo</Badge>
                  ) : (
                    <Badge variant="destructive">Inactivo</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    {canUpdate('users') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenRoleDialog(user)}
                        data-testid={`assign-roles-${index}`}
                        title="Asignar Roles"
                      >
                        <Shield className="h-4 w-4" />
                      </Button>
                    )}
                    {canUpdate('users') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenDialog(user)}
                        data-testid={`edit-user-${index}`}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                    )}
                    {canUpdate('users') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleActive(user.email, user.is_active)}
                        data-testid={`toggle-user-${index}`}
                        // El backend también lo impide; aquí se evita el clic y se explica por qué.
                        disabled={user.is_active && user.email === loggedUser?.email}
                        title={
                          user.is_active && user.email === loggedUser?.email
                            ? 'No puedes desactivar tu propia cuenta'
                            : user.is_active ? 'Desactivar usuario' : 'Activar usuario'
                        }
                      >
                        {user.is_active ? (
                          <UserX className="h-4 w-4" />
                        ) : (
                          <UserCheck className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Pagination {...list.paginationProps} noun="usuario(s)" testId="users-pagination" />

      {/* Role Assignment Dialog */}
      <Dialog open={roleDialogOpen} onOpenChange={setRoleDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Asignar Roles</DialogTitle>
            <DialogDescription>
              Selecciona los roles para {currentUser?.first_name} {currentUser?.last_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            {roles.map((role) => (
              <div key={role.name} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id={`role-${role.name}`}
                  checked={selectedUserRoles.includes(role.name)}
                  onChange={() => handleToggleRole(role.name)}
                  disabled={!role.is_active}
                />
                <Label htmlFor={`role-${role.name}`} className={!role.is_active ? 'text-muted-foreground' : ''}>
                  {role.name} {!role.is_active && '(Inactivo)'}
                  {role.description && <span className="text-xs text-muted-foreground block">{role.description}</span>}
                </Label>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRoleDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleAssignRoles} disabled={isAssigning} data-testid="save-roles-button">
              {isAssigning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Asignando...
                </>
              ) : (
                'Asignar Roles'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersManagement;