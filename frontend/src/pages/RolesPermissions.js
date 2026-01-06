import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter
} from '@/components/ui/dialog';
import { Plus, Shield, Settings, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';

const RolesPermissions = () => {
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [rolesRes, modulesRes] = await Promise.all([
        axios.get(`${API}/rbac/roles`),
        axios.get(`${API}/rbac/modules`)
      ]);
      setRoles(rolesRes.data);
      setModules(modulesRes.data);
      
      const permsMap = {};
      for (const role of rolesRes.data) {
        const permsRes = await axios.get(`${API}/rbac/permissions/${role.name}`);
        permsMap[role.name] = {};
        permsRes.data.forEach(p => {
          permsMap[role.name][p.module_slug] = p.permissions;
        });
      }
      setPermissions(permsMap);
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/rbac/roles`, formData);
      toast.success('Rol creado');
      fetchData();
      setDialogOpen(false);
      setFormData({ name: '', description: '', is_active: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al crear rol');
    }
  };

  const handleTogglePermission = async (roleName, moduleSlug, permission) => {
    try {
      const currentPerms = permissions[roleName]?.[moduleSlug] || {
        read: false,
        create: false,
        update: false,
        delete: false
      };

      const newPerms = {
        ...currentPerms,
        [permission]: !currentPerms[permission]
      };

      await axios.post(`${API}/rbac/permissions`, {
        role_name: roleName,
        module_slug: moduleSlug,
        permissions: newPerms
      });

      setPermissions(prev => ({
        ...prev,
        [roleName]: {
          ...prev[roleName],
          [moduleSlug]: newPerms
        }
      }));

      toast.success('Permiso actualizado');
    } catch (error) {
      toast.error('Error al actualizar permiso');
    }
  };

  const hasPermission = (roleName, moduleSlug, permission) => {
    return permissions[roleName]?.[moduleSlug]?.[permission] || false;
  };

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="roles-permissions-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Roles y Permisos</h1>
        <p className="text-muted-foreground mt-2">Gestiona roles y sus permisos sobre los módulos del sistema</p>
      </div>

      <Tabs defaultValue="permissions" className="space-y-4">
        <TabsList>
          <TabsTrigger value="permissions">
            <Shield className="h-4 w-4 mr-2" />
            Matriz de Permisos
          </TabsTrigger>
          <TabsTrigger value="roles">
            <Settings className="h-4 w-4 mr-2" />
            Gestionar Roles
          </TabsTrigger>
        </TabsList>

        <TabsContent value="permissions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Matriz de Permisos (Rol x Módulo)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-3 font-semibold sticky left-0 bg-card z-10">Módulo</th>
                      {roles.map(role => (
                        <th key={role.name} className="text-center p-3 font-semibold min-w-[180px]">
                          <div className="flex flex-col items-center gap-1">
                            <span>{role.name}</span>
                            {!role.is_active && <Badge variant="destructive" className="text-xs">Inactivo</Badge>}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {modules.map((module, idx) => (
                      <tr key={module.slug} className={idx % 2 === 0 ? 'bg-muted/30' : ''}>
                        <td className="p-3 font-medium sticky left-0 bg-card z-10">
                          {module.name}
                          <div className="text-xs text-muted-foreground">{module.slug}</div>
                        </td>
                        {roles.map(role => (
                          <td key={`${role.name}-${module.slug}`} className="p-2">
                            <div className="flex flex-col gap-1">
                              {['read', 'create', 'update', 'delete'].map(perm => (
                                <button
                                  key={perm}
                                  onClick={() => handleTogglePermission(role.name, module.slug, perm)}
                                  disabled={!role.is_active || !module.is_active}
                                  className={`flex items-center justify-between px-2 py-1 text-xs rounded transition-colors ${
                                    hasPermission(role.name, module.slug, perm)
                                      ? 'bg-chart-1/20 text-chart-1'
                                      : 'bg-muted text-muted-foreground'
                                  } ${role.is_active && module.is_active ? 'hover:opacity-80 cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                                >
                                  <span className="capitalize">{perm}</span>
                                  {hasPermission(role.name, module.slug, perm) ? (
                                    <Check className="h-3 w-3" />
                                  ) : (
                                    <X className="h-3 w-3" />
                                  )}
                                </button>
                              ))}
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="roles" className="space-y-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-semibold">Roles del Sistema</h2>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Nuevo Rol
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Nuevo Rol</DialogTitle>
                  <DialogDescription>Crea un nuevo rol en el sistema</DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">Nombre del Rol *</Label>
                      <Input
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">Descripción</Label>
                      <Input
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      />
                    </div>
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="is_active"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      />
                      <Label htmlFor="is_active">Rol Activo</Label>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                      Cancelar
                    </Button>
                    <Button type="submit">
                      Crear Rol
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {roles.map((role) => (
              <Card key={role.name} className="card-hover">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{role.name}</span>
                    {role.is_active ? (
                      <Badge className="bg-chart-1/20 text-chart-1">Activo</Badge>
                    ) : (
                      <Badge variant="destructive">Inactivo</Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-4">
                    {role.description || 'Sin descripción'}
                  </p>
                  <div className="text-xs text-muted-foreground">
                    Permisos asignados: {Object.keys(permissions[role.name] || {}).length} módulos
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default RolesPermissions;