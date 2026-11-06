import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Bell, Package, CreditCard, CalendarClock, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { DATA_CHANGED } from '@/lib/events';
import { API } from '@/App';

// P2.34: campana de alertas (stock bajo/agotado, créditos vencidos y por vencer).
// Las alertas se calculan en el servidor según los permisos del usuario; «Marcar como visto»
// apaga el número rojo hasta que aparezca una alerta nueva o empeore una existente.
const REFRESH_MS = 2 * 60 * 1000;
const money = (v) => `$${Number(v || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 })}`;
const todayKey = (email) => {
  const d = new Date();
  return `boltrex.alerts.summary.${email}.${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
};
const fiosLink = (i) => `/fios?doc=${encodeURIComponent(i.client_document)}${i.client_document_type ? `&type=${encodeURIComponent(i.client_document_type)}` : ''}`;

const NewDot = ({ show }) => (show ? <span className="ml-1 inline-block h-2 w-2 rounded-full bg-red-500" aria-label="nueva" /> : null);

const Group = ({ icon: Icon, title, count, children, more, onMore }) => (
  <div className="py-2">
    <div className="flex items-center gap-2 text-sm font-semibold mb-1">
      <Icon className="h-4 w-4" /> {title} <span className="text-muted-foreground font-normal">({count})</span>
    </div>
    <div className="space-y-1">{children}</div>
    {more && (
      <button type="button" onClick={onMore} className="mt-1 text-xs text-primary hover:underline flex items-center">
        {more} <ChevronRight className="h-3 w-3" />
      </button>
    )}
  </div>
);

const AlertsBell = ({ user }) => {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [marking, setMarking] = useState(false);
  const navigate = useNavigate();
  const summaryShown = useRef(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/alerts`);
      setData(r.data);
      return r.data;
    } catch {
      return null;   // la campana nunca interrumpe el trabajo; se reintenta en el próximo ciclo
    }
  }, []);

  const go = (path) => { setOpen(false); navigate(path); };

  useEffect(() => {
    let alive = true;
    load().then((d) => {
      // Resumen al entrar: una vez al día por usuario (solo es una comodidad: si el navegador
      // no guarda datos, se vuelve a mostrar).
      if (!alive || !d || !d.total || summaryShown.current) return;
      summaryShown.current = true;
      let already = false;
      try { already = !!localStorage.getItem(todayKey(user?.email)); } catch { /* sin almacenamiento */ }
      if (already) return;
      try { localStorage.setItem(todayKey(user?.email), '1'); } catch { /* sin almacenamiento */ }
      const g = d.groups || {};
      const parts = [];
      if (g.stock?.count) parts.push(`${g.stock.count} de stock`);
      if (g.overdue?.count) parts.push(`${g.overdue.count} cliente(s) con créditos vencidos`);
      if (g.due_soon?.count) parts.push(`${g.due_soon.count} factura(s) por vencer`);
      toast.warning(`Tienes alertas: ${parts.join(' · ')}`, {
        duration: 8000,
        action: { label: 'Ver', onClick: () => setOpen(true) },
      });
    });
    const id = setInterval(load, REFRESH_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') load(); };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener(DATA_CHANGED, load);
    return () => {
      alive = false;
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener(DATA_CHANGED, load);
    };
  }, [load, user]);

  const markSeen = async () => {
    setMarking(true);
    try {
      await axios.post(`${API}/alerts/seen`);
      await load();
    } catch {
      toast.error('No se pudieron marcar las alertas como vistas. Intenta de nuevo.');
    } finally {
      setMarking(false);
    }
  };

  const g = data?.groups || {};
  const total = data?.total || 0;
  const fresh = data?.new || 0;
  if (data && !data.can?.stock && !data.can?.credit) return null;   // el rol no ve nada que alertar

  return (
    <Popover open={open} onOpenChange={(o) => { setOpen(o); if (o) load(); }}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={`Alertas (${fresh} nuevas)`} data-testid="alerts-bell">
          <Bell className="h-5 w-5" />
          {fresh > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center"
                  data-testid="alerts-badge">
              {fresh > 99 ? '99+' : fresh}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[22rem] max-w-[calc(100vw-1rem)] p-0" data-testid="alerts-panel">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <span className="font-semibold">Alertas</span>
          <span className="text-xs text-muted-foreground">{total ? `${total} activa(s)${fresh ? ` · ${fresh} nueva(s)` : ''}` : ''}</span>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-4 divide-y">
          {!data && <p className="py-6 text-sm text-center text-muted-foreground">Cargando…</p>}
          {data && total === 0 && <p className="py-6 text-sm text-center text-muted-foreground">Todo en orden: no hay alertas.</p>}

          {g.stock?.count > 0 && (
            <Group icon={Package} title="Stock" count={g.stock.count}
                   more={g.stock.count > g.stock.items.length ? 'Ver todos en Inventario' : 'Ver en Inventario'}
                   onMore={() => go('/inventory?stock=low')}>
              {g.stock.items.map((i) => (
                <button key={i.barcode} type="button" onClick={() => go('/inventory?stock=low')}
                        className="w-full text-left text-sm hover:bg-muted rounded px-1 py-0.5">
                  • {i.name} — {i.status === 'out'
                    ? <span className="text-red-400">agotado</span>
                    : <span className="text-amber-400">quedan {i.stock} (mín. {i.min_stock})</span>}
                  <NewDot show={i.is_new} />
                </button>
              ))}
            </Group>
          )}

          {g.overdue?.count > 0 && (
            <Group icon={CreditCard} title="Créditos vencidos" count={g.overdue.count}
                   more={`Ver en Fios (${money(g.overdue.balance)} vencidos)`} onMore={() => go('/fios?status=overdue')}>
              {g.overdue.items.map((i) => (
                <button key={`${i.client_document_type}-${i.client_document}`} type="button" onClick={() => go(fiosLink(i))}
                        className="w-full text-left text-sm hover:bg-muted rounded px-1 py-0.5">
                  • {i.client_name} — <span className="text-red-400">{money(i.balance)}</span>
                  <span className="text-muted-foreground"> · vencido hace {i.max_days_overdue} día(s){i.invoices > 1 ? ` · ${i.invoices} facturas` : ''}</span>
                  <NewDot show={i.is_new} />
                </button>
              ))}
            </Group>
          )}

          {g.due_soon?.count > 0 && (
            <Group icon={CalendarClock} title={`Por vencer (${g.due_soon.due_soon_days} días)`} count={g.due_soon.count}
                   more={`Ver en Fios (${money(g.due_soon.balance)})`} onMore={() => go('/fios?status=due_soon')}>
              {g.due_soon.items.map((i) => (
                <button key={i.invoice_number} type="button" onClick={() => go(fiosLink(i))}
                        className="w-full text-left text-sm hover:bg-muted rounded px-1 py-0.5">
                  • {i.client_name} — {money(i.balance)} <span className="text-amber-400">· {i.label}</span>
                  <span className="text-muted-foreground font-mono text-xs"> {i.invoice_number}</span>
                  <NewDot show={i.is_new} />
                </button>
              ))}
            </Group>
          )}
        </div>
        {total > 0 && (
          <div className="px-4 py-2 border-t flex justify-end">
            <Button size="sm" variant="outline" onClick={markSeen} disabled={marking || fresh === 0} data-testid="alerts-mark-seen">
              {fresh === 0 ? 'Todo visto' : 'Marcar como visto'}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default AlertsBell;
