import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import {
  MSG_IDLE,
  getLastActivity,
  getLastServerContact,
  markActivity,
} from '@/lib/session';

// Cierre de sesión por inactividad (backlog P1.11).
//  - Cuenta como actividad: teclado, mouse, toques, scroll y cualquier petición al servidor.
//  - Si hubo actividad sin peticiones, avisa al servidor con /auth/ping ("sigo aquí").
//  - `warning_minutes` antes del cierre muestra un aviso con cuenta regresiva y "Seguir conectado".
//  - Al cumplirse `idle_minutes` cierra la sesión y el login muestra el motivo.
// El servidor aplica la misma regla: aunque esta pantalla fallara, el token deja de servir.
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'wheel', 'scroll'];
const ACTIVITY_THROTTLE_MS = 10 * 1000;

const formatRemaining = (ms) => {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(total / 60);
  const s = String(total % 60).padStart(2, '0');
  return `${m}:${s}`;
};

const SessionWatcher = ({ api, session, onExpire }) => {
  const idleMs = (session?.idle_minutes ?? 60) * 60 * 1000;
  const warnMs = (session?.warning_minutes ?? 5) * 60 * 1000;
  // "Sigo aquí" como máximo cada 4 min (o un cuarto del tiempo de inactividad si es corto).
  const heartbeatMs = Math.min(4 * 60 * 1000, idleMs / 4);

  const [remaining, setRemaining] = useState(null);
  const pinging = useRef(false);
  const lastLocalMark = useRef(0);
  const expired = useRef(false);

  const ping = async () => {
    if (pinging.current) return;
    pinging.current = true;
    try {
      await axios.post(`${api}/auth/ping`);
    } catch (error) {
      // Un 401 lo gestiona el interceptor de App (cierra la sesión con el motivo).
      if (error?.response?.status !== 401) {
        toast.error(getErrorMessage(error, 'No se pudo confirmar la sesión con el servidor'));
      }
    } finally {
      pinging.current = false;
    }
  };

  useEffect(() => {
    if (!getLastActivity()) markActivity();

    const onActivity = () => {
      const now = Date.now();
      if (now - lastLocalMark.current < ACTIVITY_THROTTLE_MS) return;
      lastLocalMark.current = now;
      markActivity();
    };
    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));

    const tick = () => {
      if (expired.current) return;
      const now = Date.now();
      const lastActivity = getLastActivity();
      const idle = now - lastActivity;

      if (idle >= idleMs) {
        expired.current = true;
        setRemaining(null);
        onExpire(MSG_IDLE);
        return;
      }
      setRemaining(idle >= idleMs - warnMs ? idleMs - idle : null);

      // Hubo actividad que el servidor aún no conoce y ya pasó el intervalo → "sigo aquí".
      const lastContact = getLastServerContact();
      if (lastActivity > lastContact + 1000 && now - lastContact >= heartbeatMs) {
        ping();
      }
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => {
      clearInterval(id);
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idleMs, warnMs, heartbeatMs]);

  if (remaining === null) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] max-w-sm rounded-lg border border-amber-500/50 bg-card p-4 shadow-lg"
      role="alertdialog"
      aria-live="assertive"
      data-testid="session-idle-warning"
    >
      <div className="flex items-start gap-3">
        <Clock className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <p className="text-sm font-semibold">Tu sesión está por cerrarse</p>
          <p className="text-sm text-muted-foreground">
            Por inactividad, la sesión se cerrará en <span className="font-mono font-semibold">{formatRemaining(remaining)}</span>.
            Lo que no hayas guardado se perderá.
          </p>
          <Button
            size="sm"
            onClick={() => {
              markActivity();
              setRemaining(null);
              ping();
            }}
            data-testid="session-keep-alive"
          >
            Seguir conectado
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SessionWatcher;
