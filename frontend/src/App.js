import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import '@/App.css';

// Pages
import Login from '@/pages/Login';
import ChangePassword from '@/pages/ChangePassword';
import Dashboard from '@/pages/Dashboard';
import Products from '@/pages/Products';
import Categories from '@/pages/Categories';
import AdjustmentReasons from '@/pages/AdjustmentReasons';
import Clients from '@/pages/Clients';
import Suppliers from '@/pages/Suppliers';
import Purchases from '@/pages/Purchases';
import Returns from '@/pages/Returns';
import POS from '@/pages/POS';
import Inventory from '@/pages/Inventory';
import Reports from '@/pages/Reports';
import Import from '@/pages/Import';
import UsersManagement from '@/pages/UsersManagement';
import RolesPermissions from '@/pages/RolesPermissions';
import Invoices from '@/pages/Invoices';
import TicketConfig from '@/pages/TicketConfig';
import PaymentMethods from '@/pages/PaymentMethods';
import Fios from '@/pages/Fios';
import FactoryReset from '@/pages/FactoryReset';
import PriceLists from '@/pages/PriceLists';
import Audit from '@/pages/Audit';
import Cash from '@/pages/Cash';
import Layout from '@/components/Layout';
import { RequireSection, HomeRoute } from '@/components/AccessGuard';
import { AuthProvider, AuthContext, CHANGE_PASSWORD_PATH } from '@/auth/AuthProvider';
import ProtectedRoute from '@/auth/ProtectedRoute';
import { ConfirmProvider } from '@/components/ConfirmDialog';
import { API } from '@/api/client';

// Mantenimiento fase 4: la sesión vive en src/auth/AuthProvider.js y el cliente del backend en
// src/api/client.js; aquí quedan solo las rutas.

// Pantalla de cada sección (las rutas, nombres y permisos están en lib/access.js).
const PAGES = {
  '/products': Products,
  '/categories': Categories,
  '/adjustment-reasons': AdjustmentReasons,
  '/clients': Clients,
  '/suppliers': Suppliers,
  '/purchases': Purchases,
  '/returns': Returns,
  '/pos': POS,
  '/cash': Cash,
  '/invoices': Invoices,
  '/fios': Fios,
  '/inventory': Inventory,
  '/reports': Reports,
  '/import': Import,
  '/payment-methods': PaymentMethods,
  '/price-lists': PriceLists,
  '/users': UsersManagement,
  '/roles': RolesPermissions,
  '/ticket-config': TicketConfig,
  '/settings': FactoryReset,
  '/audit': Audit,
};

function App() {
  return (
    <AuthProvider>
      <ConfirmProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path={CHANGE_PASSWORD_PATH}
            element={
              <ProtectedRoute>
                <ChangePassword />
              </ProtectedRoute>
            }
          />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            {/* P1.13: cada sección exige su permiso (lib/access.js); sin él se ve "No tienes acceso". */}
            <Route index element={<HomeRoute><Dashboard /></HomeRoute>} />
            {Object.entries(PAGES).map(([path, Page]) => (
              <Route key={path} path={path.slice(1)} element={<RequireSection path={path}><Page /></RequireSection>} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </ConfirmProvider>
      <Toaster position="top-right" />
    </AuthProvider>
  );
}

export default App;
// Compatibilidad: algunas pantallas aún importan estos nombres desde '@/App'.
export { API, AuthContext };
