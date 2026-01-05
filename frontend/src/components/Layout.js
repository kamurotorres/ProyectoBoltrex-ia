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

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/products', icon: Package, label: 'Productos' },
    { path: '/categories', icon: FolderOpen, label: 'Categorías' },
    { path: '/clients', icon: Users, label: 'Clientes' },
    { path: '/suppliers', icon: Truck, label: 'Proveedores' },
    { path: '/purchases', icon: ShoppingBag, label: 'Compras' },
    { path: '/returns', icon: RotateCcw, label: 'Devoluciones' },
    { path: '/pos', icon: ShoppingCart, label: 'POS' },
    { path: '/inventory', icon: Warehouse, label: 'Inventario' },
    { path: '/reports', icon: FileText, label: 'Reportes' }
  ];

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