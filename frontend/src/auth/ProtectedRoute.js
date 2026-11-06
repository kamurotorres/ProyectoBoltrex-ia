import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { AuthContext, CHANGE_PASSWORD_PATH } from '@/auth/AuthProvider';

// Protected Route: exige sesión y, si la contraseña está pendiente de cambio, solo deja ver esa pantalla.
export const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  const { user } = React.useContext(AuthContext);
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (user?.must_change_password && location.pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />;
  }
  return children;
};

export default ProtectedRoute;
