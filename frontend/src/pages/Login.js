import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext, API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();

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
        login(response.data.access_token, response.data.user);
        toast.success('¡Bienvenido a Boltrex!');
        navigate('/');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error en la autenticación');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center relative"
      style={{
        backgroundImage: 'url(https://images.unsplash.com/photo-1601277743437-2b4cf99aab99?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBkYXJrJTIwd2FyZWhvdXNlJTIwYWJzdHJhY3QlMjB0ZWNobm9sb2d5fGVufDB8fHx8MTc2NzYzMDYzMXww&ixlib=rb-4.1.0&q=85)',
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }}
    >
      <div className="absolute inset-0 bg-black/60" />
      
      <Card className="w-full max-w-md relative z-10 border-white/10" data-testid="login-card">
        <CardHeader className="space-y-1">
          <CardTitle className="text-3xl font-bold tracking-tight">
            {isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'}
          </CardTitle>
          <CardDescription className="text-base">
            {isRegister ? 'Registra tu cuenta en Boltrex' : 'Accede a tu sistema Boltrex'}
          </CardDescription>
        </CardHeader>
        <CardContent>
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
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;