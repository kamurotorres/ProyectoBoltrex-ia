import React, { useState, useContext } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '@/App';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
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
  KeyRound,
  ScrollText,
  Banknote,
  Receipt,
  Settings,
  CreditCard,
  Wallet,
  DollarSign,
  SlidersHorizontal,
  Menu,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { allowedSections, findSection, isReadOnly } from '@/lib/access';
import BoltrexLogo from '@/components/BoltrexLogo';
import AlertsBell from '@/components/AlertsBell';

const ICONS = {
  LayoutDashboard, Package, FolderOpen, Users, Truck, ShoppingBag, RotateCcw, ShoppingCart, Receipt,
  Wallet, Warehouse, FileText, Upload, CreditCard, DollarSign, UserCog, Shield, Settings, ScrollText, Banknote,
  SlidersHorizontal,
};

const Layout = () => {
  const { user, logout, logoutAll } = useContext(AuthContext);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const readOnly = isReadOnly(user, findSection(location.pathname));

  const handleLogout = () => {
    setSidebarOpen(false);
    logout();
    navigate('/login');
  };

  // Cierra la sesión en todos los equipos (útil si se perdió un equipo o se usó uno ajeno).
  const handleLogoutAll = async () => {
    if (!window.confirm('¿Cerrar tu sesión en TODOS los equipos, incluido este? Tendrás que volver a iniciar sesión.')) return;
    setSidebarOpen(false);
    try {
      await logoutAll();
      navigate('/login');
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cerrar la sesión en todos los equipos'));
    }
  };

  // Menú = secciones que el usuario puede ver, del mapa único lib/access.js (P1.13).
  const navItems = allowedSections(user).map((section) => ({
    ...section,
    icon: ICONS[section.icon] || Settings,
  }));

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
            <BoltrexLogo size={24} />
            <span className="font-bold text-lg tracking-tight">Boltrex</span>
            <span className="text-xs text-muted-foreground hidden sm:inline">| POS e inventario</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* P2.34: alertas de stock y créditos */}
          {user && <AlertsBell user={user} />}
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
          <div className="flex items-center gap-2">
            <BoltrexLogo size={28} />
            <div>
            <h1 className="text-xl font-bold tracking-tight" data-testid="app-title">
              Boltrex
            </h1>
            <p className="text-xs text-muted-foreground">Inventario y POS</p>
            </div>
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
              <button
                type="button"
                onClick={handleLogoutAll}
                className="text-[10px] text-muted-foreground hover:text-destructive hover:underline"
                data-testid="logout-all-button"
                title="Cerrar la sesión en todos los equipos donde hayas entrado"
              >
                Cerrar sesión en todos los equipos
              </button>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setSidebarOpen(false); navigate('/change-password'); }}
              className="h-8 px-2 text-xs flex items-center gap-1 shrink-0"
              data-testid="change-password-button"
              title="Cambiar mi contraseña"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span>Contraseña</span>
            </Button>
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
        {/* P1.13: el rol puede ver esta sección pero no crear, editar ni eliminar. */}
        {readOnly && (
          <div className="mb-4 rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm" role="status" data-testid="read-only-banner">
            <span className="font-semibold">Solo lectura.</span> Tu rol puede ver esta sección, pero no crear, editar ni eliminar. Si lo necesitas, pídeselo a un administrador.
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;