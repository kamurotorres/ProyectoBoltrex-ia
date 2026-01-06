import React, { useContext } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { AuthContext } from '@/App';
import {
  LayoutDashboard,
  Package,
  FolderOpen,
  Users,
  Truck,
  ShoppingBag,
  RotateCcw,
  ShoppingCart,
  Warehouse,
  FileText,
  Upload,
  UserCog,
  Shield,
  LogOut
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const Layout = () => {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Map routes to module slugs
  const routeToModuleMap = {
    '/': 'dashboard',
    '/products': 'products',
    '/categories': 'categories',
    '/clients': 'clients',
    '/suppliers': 'suppliers',
    '/purchases': 'purchases',
    '/returns': 'returns',
    '/pos': 'pos',
    '/inventory': 'inventory',
    '/reports': 'reports',
    '/import': 'import',
    '/users': 'users',
    '/roles': 'permissions'
  };

  const allNavItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard', moduleSlug: 'dashboard' },
    { path: '/products', icon: Package, label: 'Productos', moduleSlug: 'products' },
    { path: '/categories', icon: FolderOpen, label: 'Categorías', moduleSlug: 'categories' },
    { path: '/clients', icon: Users, label: 'Clientes', moduleSlug: 'clients' },
    { path: '/suppliers', icon: Truck, label: 'Proveedores', moduleSlug: 'suppliers' },
    { path: '/purchases', icon: ShoppingBag, label: 'Compras', moduleSlug: 'purchases' },
    { path: '/returns', icon: RotateCcw, label: 'Devoluciones', moduleSlug: 'returns' },
    { path: '/pos', icon: ShoppingCart, label: 'POS', moduleSlug: 'pos' },
    { path: '/inventory', icon: Warehouse, label: 'Inventario', moduleSlug: 'inventory' },
    { path: '/reports', icon: FileText, label: 'Reportes', moduleSlug: 'reports' },
    { path: '/import', icon: Upload, label: 'Importar', moduleSlug: 'import' },
    { path: '/users', icon: UserCog, label: 'Usuarios', moduleSlug: 'users' },
    { path: '/roles', icon: Shield, label: 'Roles y Permisos', moduleSlug: 'permissions' }
  ];

  // Filter nav items based on user permissions
  const navItems = allNavItems.filter(item => {
    if (!user || !user.permissions) return false;
    
    const modulePermissions = user.permissions[item.moduleSlug];
    
    // User needs at least READ permission to see the module
    return modulePermissions && modulePermissions.read === true;
  });

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-60 bg-card border-r border-border fixed h-full overflow-y-auto">
        <div className="p-6 border-b border-border">
          <h1 className="text-2xl font-bold tracking-tight" data-testid="app-title">
            Boltrex
          </h1>
          <p className="text-xs text-muted-foreground mt-1">Inventory & POS</p>
        </div>

        <nav className="p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `sidebar-nav-item flex items-center gap-3 px-4 py-3 rounded-md text-sm ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase()}`}
            >
              <item.icon className="h-5 w-5" strokeWidth={1.5} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border bg-card">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" data-testid="user-email">{user?.email}</p>
              <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleLogout}
              data-testid="logout-button"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-60">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;