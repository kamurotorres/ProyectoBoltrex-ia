import React, { useState, useContext } from 'react';
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
  LogOut,
  Receipt,
  Settings,
  CreditCard,
  Wallet,
  DollarSign,
  Menu,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const Layout = () => {
  const { user, logout } = useContext(AuthContext);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    setSidebarOpen(false);
    logout();
    navigate('/login');
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
    { path: '/invoices', icon: Receipt, label: 'Facturas', moduleSlug: 'invoices' },
    { path: '/fios', icon: Wallet, label: 'Fios (Créditos)', moduleSlug: 'fios' },
    { path: '/inventory', icon: Warehouse, label: 'Inventario', moduleSlug: 'inventory' },
    { path: '/reports', icon: FileText, label: 'Reportes', moduleSlug: 'reports' },
    { path: '/import', icon: Upload, label: 'Importar', moduleSlug: 'import' },
    { path: '/payment-methods', icon: CreditCard, label: 'Formas de Pago', moduleSlug: 'payment-methods' },
    { path: '/price-lists', icon: DollarSign, label: 'Listas de Precios', moduleSlug: 'price-lists' },
    { path: '/users', icon: UserCog, label: 'Usuarios', moduleSlug: 'users' },
    { path: '/roles', icon: Shield, label: 'Roles y Permisos', moduleSlug: 'permissions' },
    { path: '/ticket-config', icon: Settings, label: 'Config. Tickets', moduleSlug: 'ticket-config' },
    { path: '/settings', icon: Settings, label: 'Config. Sistema', moduleSlug: 'permissions' }
  ];

  // Filter nav items based on user permissions
  const navItems = allNavItems.filter(item => {
    if (!user || !user.permissions) return false;
    const modulePermissions = user.permissions[item.moduleSlug];
    return modulePermissions && modulePermissions.read === true;
  });

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Backdrop overlay when sidebar is open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 backdrop-blur-xs transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Top Header Bar with Hamburger Button */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-card/75">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSidebarOpen(prev => !prev)}
            className="flex items-center gap-2 font-medium"
            data-testid="hamburger-menu-button"
            title="Abrir menú"
          >
            <Menu className="h-4 w-4" />
            <span className="text-xs sm:text-sm font-semibold">Menú</span>
          </Button>
          <div className="flex items-center gap-2">
            <span className="font-bold text-lg tracking-tight">Boltrex</span>
            <span className="text-xs text-muted-foreground hidden sm:inline">| POS & Gestión</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden md:inline font-mono">{user?.email}</span>
        </div>
      </header>

      {/* Slide-out Sidebar Drawer */}
      <aside
        className={`fixed top-0 left-0 h-full w-64 bg-card border-r border-border z-50 flex flex-col shadow-2xl transition-transform duration-300 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight" data-testid="app-title">
              Boltrex
            </h1>
            <p className="text-xs text-muted-foreground">Inventory & POS</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            title="Cerrar menú"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* User Info & Logout Button at the TOP, right below program name */}
        <div className="p-3 border-b border-border bg-muted/40">
          <div className="flex items-center justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold truncate text-foreground" data-testid="user-email">
                {user?.email}
              </p>
              <p className="text-[10px] text-muted-foreground capitalize truncate">
                {user?.roles && user.roles.length > 0 ? user.roles.join(', ') : (user?.role || 'Usuario')}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="h-8 px-2 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive flex items-center gap-1 shrink-0"
              data-testid="logout-button"
              title="Cerrar sesión"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Salir</span>
            </Button>
          </div>
        </div>

        {/* Navigation List - Closes sidebar upon clicking any item */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `sidebar-nav-item flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase()}`}
            >
              <item.icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main Content Area - Full width */}
      <main className="flex-1 p-4 md:p-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;