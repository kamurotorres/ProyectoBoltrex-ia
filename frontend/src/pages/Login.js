import React, { useState, useContext, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext, API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import BoltrexLogo from '@/components/BoltrexLogo';
import { takeLogoutReason } from '@/lib/session';

// El registro público está desactivado en el backend por defecto (ALLOW_PUBLIC_REGISTRATION).
// Para mostrar el enlace "Regístrate", construir el frontend con REACT_APP_ALLOW_REGISTRATION=true.
const ALLOW_REGISTRATION = process.env.REACT_APP_ALLOW_REGISTRATION === 'true';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();
  // Motivo del último cierre de sesión (inactividad, sesión cerrada desde otro equipo, etc.).
  const [logoutReason, setLogoutReason] = useState(null);
  useEffect(() => {
    const reason = takeLogoutReason();
    if (reason) {
      setLogoutReason(reason);
      toast.info(reason);
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isRegister) {
        await axios.post(`${API}/auth/register`, {
          email,
          password,
          full_name: fullName,
          role: 'admin'
        });
        toast.success('Cuenta creada exitosamente. Por favor inicia sesión.');
        setIsRegister(false);
      } else {
        const response = await axios.post(`${API}/auth/login`, { email, password });
        login(response.data.access_token, response.data.user, response.data.session);
        if (response.data.user?.must_change_password) {
          toast.warning('Por seguridad debes cambiar tu contraseña antes de continuar.');
          navigate('/change-password');
        } else {
          toast.success('¡Bienvenido a Boltrex!');
          navigate('/');
        }
      }
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error en la autenticación'));
    } finally {
      setLoading(false);
    }
  };

  return (
    // P2.27: fondo propio (degradado oscuro + rayo), sin imágenes externas.
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden px-4 bg-[radial-gradient(ellipse_at_top,_#14532d55,_transparent_55%),linear-gradient(160deg,#09090b_0%,#111114_55%,#052e16_100%)]">
      <svg aria-hidden="true" className="pointer-events-none absolute -right-24 -bottom-24 h-[28rem] w-[28rem] opacity-[0.06]" viewBox="0 0 64 64">
        <path d="M36 8 L16 36 H30 L26 56 L48 26 H34 Z" fill="#22c55e" />
      </svg>

      <Card className="w-full max-w-md relative z-10 border-white/10" data-testid="login-card">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2 mb-2">
            <BoltrexLogo size={36} />
            <span className="text-xl font-bold tracking-tight">Boltrex</span>
          </div>
          <CardTitle className="text-3xl font-bold tracking-tight">
            {isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'}
          </CardTitle>
          <CardDescription className="text-base">
            {isRegister ? 'Registra tu cuenta en Boltrex' : 'Accede a tu sistema Boltrex'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {logoutReason && (
            <div className="mb-4 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm" role="status" data-testid="logout-reason">
              {logoutReason}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div className="space-y-2">
                <Label htmlFor="fullName">Nombre Completo</Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="Juan Pérez"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  data-testid="fullname-input"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="usuario@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="password-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              data-testid="submit-button"
            >
              {loading ? 'Procesando...' : isRegister ? 'Registrarse' : 'Iniciar Sesión'}
            </Button>
          </form>

          {ALLOW_REGISTRATION && (
            <div className="mt-4 text-center text-sm">
              <button
                type="button"
                onClick={() => setIsRegister(!isRegister)}
                className="text-primary hover:underline"
                data-testid="toggle-auth-mode"
              >
                {isRegister ? '¿Ya tienes cuenta? Inicia sesión' : '¿No tienes cuenta? Regístrate'}
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;