import { useContext } from 'react';
import { AuthContext } from '@/App';

/**
 * Hook personalizado para verificar permisos del usuario
 */
export const usePermissions = () => {
  const { user } = useContext(AuthContext);

  const hasPermission = (moduleSlug, action) => {
    if (!user || !user.permissions) return false;
    
    const modulePermissions = user.permissions[moduleSlug];
    if (!modulePermissions) return false;

    return modulePermissions[action] === true;
  };

  const canRead = (moduleSlug) => hasPermission(moduleSlug, 'read');
  const canCreate = (moduleSlug) => hasPermission(moduleSlug, 'create');
  const canUpdate = (moduleSlug) => hasPermission(moduleSlug, 'update');
  const canDelete = (moduleSlug) => hasPermission(moduleSlug, 'delete');

  const hasAnyPermission = (moduleSlug) => {
    if (!user || !user.permissions) return false;
    const modulePermissions = user.permissions[moduleSlug];
    return modulePermissions && (
      modulePermissions.read ||
      modulePermissions.create ||
      modulePermissions.update ||
      modulePermissions.delete
    );
  };

  return {
    hasPermission,
    canRead,
    canCreate,
    canUpdate,
    canDelete,
    hasAnyPermission,
    permissions: user?.permissions || {},
    roles: user?.roles || []
  };
};
