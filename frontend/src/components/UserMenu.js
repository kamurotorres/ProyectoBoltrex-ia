import React from 'react';
import { KeyRound, LogOut, MonitorSmartphone } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

// Menú «Mi cuenta» (rama menu-por-grupos): iniciales del usuario arriba a la derecha → cambiar contraseña,
// cerrar sesión en todos los equipos y cerrar sesión. Es de CADA usuario (no de Config. Sistema, que es solo admin).

/** «Ana Ruiz» → «AR» · «ana@tienda.com» → «AN». */
export const initials = (user) => {
  const name = (user?.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`).trim();
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (user?.email || '?').slice(0, 2).toUpperCase();
};

export const displayName = (user) => (user?.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`).trim() || user?.email || '';
export const rolesText = (user) => (user?.roles && user.roles.length > 0 ? user.roles.join(', ') : (user?.role || 'Usuario'));

export default function UserMenu({ user, onChangePassword, onLogoutAll, onLogout }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-border bg-muted/40 pl-1 pr-2 py-1 hover:bg-muted transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title="Mi cuenta"
          data-testid="user-menu-button"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
            {initials(user)}
          </span>
          <span className="text-xs text-muted-foreground hidden md:inline max-w-[160px] truncate">{displayName(user)}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <p className="text-sm font-semibold truncate" data-testid="user-menu-name">{displayName(user)}</p>
          <p className="text-xs text-muted-foreground truncate" data-testid="user-email">{user?.email}</p>
          <p className="text-xs text-muted-foreground truncate">{rolesText(user)}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onChangePassword} data-testid="change-password-button">
          <KeyRound className="h-4 w-4 mr-2" />
          Cambiar contraseña
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onLogoutAll} data-testid="logout-all-button">
          <MonitorSmartphone className="h-4 w-4 mr-2" />
          Cerrar sesión en todos los equipos
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onLogout} className="text-destructive focus:text-destructive" data-testid="logout-button">
          <LogOut className="h-4 w-4 mr-2" />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
