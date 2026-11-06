// Sesión del usuario (mantenimiento fase 4: sacado de App.js tal cual).
// Contexto con { user, login, logout, logoutAll, markPasswordChanged }, interceptores de axios
// (sesión vencida → login; contraseña por cambiar; permisos que cambiaron), cierre en otras pestañas
// y refresco de permisos al volver a la pestaña. También muestra el aviso de inactividad (SessionWatcher).
import React, { useContext, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { API } from '@/api/client';
import SessionWatcher from '@/components/SessionWatcher';
import { markServerContact, setLogoutReason } from '@/lib/session';

// Mensaje exacto con el que el backend rechaza las acciones de quien debe cambiar su contraseña (P1.10).
export const PASSWORD_CHANGE_REQUIRED = 'Debes cambiar tu contraseña antes de continuar.';
export const CHANGE_PASSWORD_PATH = '/change-password';

export const AuthContext = React.createContext(null);

/** Acceso a la sesión desde cualquier componente: const { user, logout } = useAuth(); */
export const useAuth = () => useContext(AuthContext);

// Peticiones cuyo 401 NO significa "sesión cerrada" (credenciales incorrectas en el login).
const isLoginRequest = (config) => /\/auth\/login$/.test(config?.url || '');
// Mensajes de core/sessions.py y core/security.py que significan "la sesión ya no sirve".
const isSessionError = (detail) => typeof detail === 'string' && (detail.startsWith('Tu sesión') || detail.startsWith('Sesión no válida'));
// Mensaje de core/permissions.py: el rol perdió un permiso → se refrescan los permisos (P1.13).
const PERMISSION_DENIED = 'No tienes permiso para realizar esta acción';
// Al volver a la pestaña tras este tiempo se refrescan los permisos.
const REFRESH_AFTER_HIDDEN_MS = 60 * 1000;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Cierre local de la sesión; `reason` se muestra en la pantalla de login.
  const clearSession = (reason) => {
    setLogoutReason(reason);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };

  useEffect(() => {
    // Toda petición cuenta como actividad (P1.11): la inactividad se mide desde la última.
    const reqId = axios.interceptors.request.use((config) => {
      if (localStorage.getItem('token')) markServerContact();
      return config;
    });
    const resId = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail;
        // Contraseña pendiente de cambio (P1.10): ProtectedRoute lleva a la pantalla de cambio.
        if (status === 403 && detail === PASSWORD_CHANGE_REQUIRED) {
          setUser((prev) => (prev ? { ...prev, must_change_password: true } : prev));
        }
        // Permiso denegado: puede que un admin le haya cambiado los permisos al rol.
        if (status === 403 && detail === PERMISSION_DENIED) {
          refreshPermissionsRef.current();
        }
        // Sesión cerrada en el servidor (inactividad, vencida, cerrada desde otro equipo, etc.).
        // Solo los mensajes de sesión: otros 401 (p. ej. contraseña incorrecta al confirmar el
        // factory reset) no deben sacar al usuario de la app.
        if (status === 401 && !isLoginRequest(error.config) && isSessionError(detail) && localStorage.getItem('token')) {
          clearSession(typeof detail === 'string' ? detail : 'Tu sesión expiró. Inicia sesión de nuevo.');
        }
        return Promise.reject(error);
      }
    );
    // Si se cierra la sesión en otra pestaña, se cierra también en esta.
    const onStorage = (e) => {
      if (e.key === 'token' && !e.newValue) {
        delete axios.defaults.headers.common['Authorization'];
        setUser(null);
      }
    };
    window.addEventListener('storage', onStorage);
    // Al volver a la pestaña después de un rato, se traen los permisos actuales.
    let hiddenAt = null;
    const onVisibility = () => {
      if (document.hidden) {
        hiddenAt = Date.now();
      } else if (hiddenAt && Date.now() - hiddenAt >= REFRESH_AFTER_HIDDEN_MS) {
        hiddenAt = null;
        refreshPermissionsRef.current();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      axios.interceptors.request.eject(reqId);
      axios.interceptors.response.eject(resId);
      window.removeEventListener('storage', onStorage);
      document.removeEventListener('visibilitychange', onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
    } finally {
      setLoading(false);
    }
  };

  // Vuelve a pedir el usuario y sus permisos sin cerrar la sesión (P1.13). Como mucho una
  // vez cada 5 s, aunque fallen varias peticiones a la vez.
  const lastRefresh = useRef(0);
  const refreshPermissions = async () => {
    if (!localStorage.getItem('token') || Date.now() - lastRefresh.current < 5000) return;
    lastRefresh.current = Date.now();
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser((prev) => (prev ? { ...prev, ...response.data } : prev));
    } catch {
      // Un 401 de sesión ya lo gestiona el interceptor.
    }
  };
  const refreshPermissionsRef = useRef(refreshPermissions);
  refreshPermissionsRef.current = refreshPermissions;

  const login = (token, userData, session) => {
    localStorage.setItem('token', token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    markServerContact();
    setUser(session ? { ...userData, session } : userData);
  };

  const markPasswordChanged = () => {
    setUser((prev) => (prev ? { ...prev, must_change_password: false } : prev));
  };

  // Cierra la sesión en el servidor (el token deja de servir) y luego en el navegador.
  const logout = async (reason) => {
    if (localStorage.getItem('token')) {
      try {
        await axios.post(`${API}/auth/logout`);
      } catch {
        // Si ya estaba cerrada en el servidor no importa: se cierra igual en el navegador.
      }
    }
    clearSession(reason);
  };

  // Cierra la sesión en todos los equipos del usuario (incluido este).
  const logoutAll = async () => {
    const response = await axios.post(`${API}/auth/logout-all`);
    clearSession(response.data?.message || 'Se cerró la sesión en todos los equipos.');
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl font-mono">Loading...</div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, logoutAll, markPasswordChanged }}>
      {children}
      {user && localStorage.getItem('token') && (
        <SessionWatcher api={API} session={user.session} onExpire={(reason) => logout(reason)} />
      )}
    </AuthContext.Provider>
  );
}

export default AuthProvider;
