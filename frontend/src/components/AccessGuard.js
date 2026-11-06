import React, { useContext, useEffect, useRef } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { canAccessSection, findSection, homePath } from '@/lib/access';
import { api } from '@/api/client';
import { AuthContext } from '@/auth/AuthProvider';

// Rutas protegidas por permiso (backlog P1.13).

const Card = ({ children, testId }) => (
  <div className="flex items-center justify-center py-16 px-4" data-testid={testId}>
    <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 text-center space-y-4 shadow-sm">
      {children}
    </div>
  </div>
);

export const NoSections = () => {
  const { logout } = useContext(AuthContext);
  const navigate = useNavigate();
  return (
    <Card testId="no-sections">
      <Lock className="h-10 w-10 mx-auto text-muted-foreground" />
      <h2 className="text-lg font-semibold">Sin secciones asignadas</h2>
      <p className="text-sm text-muted-foreground">
        Tu usuario no tiene secciones asignadas. Contacta a un administrador para que te dé acceso.
      </p>
      <Button variant="outline" onClick={async () => { await logout(); navigate('/login'); }}>
        Cerrar sesión
      </Button>
    </Card>
  );
};

export const AccessDenied = ({ path, section }) => {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const reported = useRef(false);
  const home = homePath(user);
  const name = section?.label || path;

  // Se deja constancia en la auditoría (una vez por visita; el backend además evita repetidos).
  useEffect(() => {
    if (reported.current) return;
    reported.current = true;
    api.post(`/audit/access-denied`, { path, section: section?.label || null }).catch(() => {});
  }, [path, section]);

  return (
    <Card testId="access-denied">
      <Lock className="h-10 w-10 mx-auto text-amber-500" />
      <h2 className="text-lg font-semibold">No tienes acceso a "{name}"</h2>
      <p className="text-sm text-muted-foreground">
        {section?.adminOnly
          ? 'Esta sección es solo para administradores.'
          : 'Tu rol no tiene permiso para ver esta sección.'}{' '}
        Si lo necesitas, pídeselo a un administrador.
      </p>
      {home ? (
        <Button onClick={() => navigate(home, { replace: true })} data-testid="go-home">
          Ir a mi pantalla de inicio
        </Button>
      ) : (
        <p className="text-sm text-muted-foreground">Tu usuario no tiene secciones asignadas.</p>
      )}
    </Card>
  );
};

/** Muestra la pantalla solo si el usuario puede ver esa sección. */
export const RequireSection = ({ path, children }) => {
  const { user } = useContext(AuthContext);
  const section = findSection(path);
  if (canAccessSection(user, section)) return children;
  return <AccessDenied path={path} section={section} />;
};

/** Ruta "/": el Dashboard si puede verlo; si no, su primera sección permitida. */
export const HomeRoute = ({ children }) => {
  const { user } = useContext(AuthContext);
  if (canAccessSection(user, findSection('/'))) return children;
  const home = homePath(user);
  return home ? <Navigate to={home} replace /> : <NoSections />;
};
