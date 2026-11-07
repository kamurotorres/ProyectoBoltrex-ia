import React, { useState, useContext } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
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
  Ticket,
  ChevronDown,
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
import { findSection, isReadOnly, menuGroups } from '@/lib/access';
import UserMenu, { displayName, rolesText } from '@/components/UserMenu';
import BoltrexLogo from '@/components/BoltrexLogo';
import AlertsBell from '@/components/AlertsBell';
import { AuthContext } from '@/auth/AuthProvider';
import { useConfirm } from '@/components/ConfirmDialog';

const ICONS = {
  LayoutDashboard, Package, FolderOpen, Users, Truck, ShoppingBag, RotateCcw, ShoppingCart, Receipt,
  Wallet, Warehouse, FileText, Upload, CreditCard, DollarSign, UserCog, Shield, Settings, ScrollText, Banknote,
  SlidersHorizontal, Ticket,
};

// «Configuración» plegada o abierta: preferencia de cada usuario en este navegador (si no se puede guardar, no pasa nada).
const CONFIG_OPEN_KEY = 'boltrex.menu.configOpen';
const readConfigOpen = () => { try { return localStorage.getItem(CONFIG_OPEN_KEY) === '1'; } catch { return false; } };
const saveConfigOpen = (open) => { try { localStorage.setItem(CONFIG_OPEN_KEY, open ? '1' : '0'); } catch { /* sin almacenamiento */ } };

const Layout = () => {
  const { user, logout, logoutAll } = useContext(AuthContext);
  const confirm = useConfirm();   // fase 4: confirmación con el estilo de la app
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
    if (!(await confirm('¿Cerrar tu sesión en TODOS los equipos, incluido este? Tendrás que volver a iniciar sesión.', { confirmLabel: 'Cerrar todas las sesiones', destructive: true }))) return;
    setSidebarOpen(false);
    try {
      await logoutAll();
      navigate('/login');
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cerrar la sesión en todos los equipos'));
    }
  };

  // Menú = secciones que el usuario puede ver, del mapa único lib/access.js (P1.13), por grupos (menu-por-grupos).
  const groups = menuGroups(user);
  const [configOpen, setConfigOpen] = useState(readConfigOpen);
  const toggleGroup = () => { setConfigOpen((open) => { saveConfigOpen(!open); return !open; }); };
  const currentSection = findSection(location.pathname.split('/').slice(0, 2).join('/') || '/');
  const goChangePassword = () => { setSidebarOpen(false); navigate('/change-password'); };

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
          {user && <UserMenu user={user} onChangePassword={goChangePassword} onLogoutAll={handleLogoutAll} onLogout={handleLogout} />}
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

        {/* Usuario (las opciones de la cuenta están en «Mi cuenta», arriba a la derecha) */}
        <div className="px-4 py-3 border-b border-border bg-muted/40">
          <p className="text-xs font-semibold truncate text-foreground" data-testid="sidebar-user-name">{displayName(user)}</p>
          <p className="text-[10px] text-muted-foreground truncate">{rolesText(user)}</p>
        </div>

        {/* Navigation List - Closes sidebar upon clicking any item */}
        <nav className="flex-1 p-3 overflow-y-auto" data-testid="sidebar-nav">
          {groups.map((group) => {
            // Configuración se abre sola si la pantalla actual es de ese grupo.
            const open = !group.collapsible || configOpen || currentSection?.group === group.key;
            return (
              <div key={group.key} className="mb-3" data-testid={`nav-group-${group.key}`}>
                {group.label && (group.collapsible ? (
                  <button type="button" onClick={toggleGroup}
                          className="w-full flex items-center justify-between px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
                          aria-expanded={open} data-testid={`nav-group-toggle-${group.key}`}>
                    {group.label}
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? '' : '-rotate-90'}`} />
                  </button>
                ) : (
                  <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{group.label}</p>
                ))}
                {open && group.subgroups.map((sub) => (
                  <div key={sub.label || 'all'} className="space-y-1">
                    {sub.label && <p className="px-3 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/70">{sub.label}</p>}
                    {sub.sections.map((item) => {
                      const Icon = ICONS[item.icon] || Settings;
                      return (
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
                          <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
                          <span>{item.label}</span>
                        </NavLink>
                      );
                    })}
                  </div>
                ))}
              </div>
            );
          })}
        </nav>

        {/* Salir a un toque desde el menú (también está en «Mi cuenta») */}
        <div className="p-3 border-t border-border">
          <Button variant="ghost" size="sm" onClick={handleLogout}
                  className="w-full justify-start text-destructive hover:bg-destructive/10 hover:text-destructive"
                  data-testid="sidebar-logout-button">
            <LogOut className="h-4 w-4 mr-2" />
            Cerrar sesión
          </Button>
        </div>
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