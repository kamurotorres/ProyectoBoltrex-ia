import { useContext } from 'react';
import { AuthContext } from '@/App';
import { can, canAny, isAdmin } from '@/lib/access';

/**
 * Permisos del usuario actual (backlog P1.13). Uso en una pantalla:
 *
 *   const { canCreate, canUpdate, canDelete } = usePermissions();
 *   {canCreate('products') && <Button>Nuevo producto</Button>}
 *
 * Solo controla qué se MUESTRA; el backend vuelve a validar cada acción.
 */
export const usePermissions = () => {
  const { user } = useContext(AuthContext);

  const hasPermission = (moduleSlug, action) => can(user, moduleSlug, action);
  const canRead = (moduleSlug) => can(user, moduleSlug, 'read');
  const canCreate = (moduleSlug) => can(user, moduleSlug, 'create');
  const canUpdate = (moduleSlug) => can(user, moduleSlug, 'update');
  const canDelete = (moduleSlug) => can(user, moduleSlug, 'delete');

  const hasAnyPermission = (moduleSlug) =>
    ['read', 'create', 'update', 'delete'].some((action) => can(user, moduleSlug, action));

  return {
    hasPermission,
    canRead,
    canCreate,
    canUpdate,
    canDelete,
    canAny: (...pairs) => canAny(user, ...pairs),
    hasAnyPermission,
    isAdmin: isAdmin(user),
    permissions: user?.permissions || {},
    roles: user?.roles || [],
  };
};
