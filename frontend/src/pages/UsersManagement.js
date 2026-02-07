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
import { Plus, Search, Edit, UserX, UserCheck, Shield } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { usePermissions } from '@/hooks/usePermissions';

const UsersManagement = () => {
  const { canCreate, canUpdate } = usePermissions();
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [roleDialogOpen, setRoleDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [selectedUserRoles, setSelectedUserRoles] = useState([]);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    is_active: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, rolesRes] = await Promise.all([
        axios.get(`${API}/rbac/users`),
        axios.get(`${API}/rbac/roles`)
      ]);
      setUsers(usersRes.data);
      setRoles(rolesRes.data);
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editMode) {
        await axios.put(`${API}/rbac/users/${currentUser.email}`, formData);
        toast.success('Usuario actualizado');
      } else {
        await axios.post(`${API}/rbac/users`, formData);
        toast.success('Usuario creado');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar usuario');
    }
  };

  const handleOpenDialog = (user = null) => {
    if (user) {
      setEditMode(true);
      setCurrentUser(user);
      setFormData({
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
      setFormData({
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        phone: '',
        is_active: true
      });
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
      await axios.put(`${API}/rbac/users/${email}`, { is_active: !isActive });
      toast.success(isActive ? 'Usuario desactivado' : 'Usuario activado');
      fetchData();
    } catch (error) {
      toast.error('Error al cambiar estado del usuario');
    }
  };

  const handleOpenRoleDialog = (user) => {
    setCurrentUser(user);
    setSelectedUserRoles(user.roles || []);
    setRoleDialogOpen(true);
  };

  const handleAssignRoles = async () => {
    try {
      await axios.post(`${API}/rbac/users/${currentUser.email}/roles`, selectedUserRoles);
      toast.success('Roles asignados correctamente');
      fetchData();
      setRoleDialogOpen(false);
    } catch (error) {
      toast.error('Error al asignar roles');
    }
  };

  const handleToggleRole = (roleName) => {
    if (selectedUserRoles.includes(roleName)) {
      setSelectedUserRoles(selectedUserRoles.filter(r => r !== roleName));
    } else {
      setSelectedUserRoles([...selectedUserRoles, roleName]);
    }
  };

  const filteredUsers = users.filter(u =>
    search === '' ||
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    u.first_name.toLowerCase().includes(search.toLowerCase()) ||
    u.last_name.toLowerCase().includes(search.toLowerCase())
  );

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
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">Nombres *</Label>
                    <Input
                      id="first_name"
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                      required
                      data-testid="user-first-name-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last_name">Apellidos *</Label>
                    <Input
                      id="last_name"
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                      required
                      data-testid="user-last-name-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                    disabled={editMode}
                    data-testid="user-email-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">{editMode ? 'Nueva Contraseña (opcional)' : 'Contraseña *'}</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    required={!editMode}
                    data-testid="user-password-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone">Teléfono</Label>
                  <Input
                    id="phone"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    data-testid="user-phone-input"
                  />
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    data-testid="user-active-checkbox"
                  />
                  <Label htmlFor="is_active">Usuario Activo</Label>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                <Button type="submit" data-testid="save-user-button">
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
            placeholder="Buscar usuarios..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
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
            <Button onClick={handleAssignRoles} data-testid="save-roles-button">
              Asignar Roles
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersManagement;