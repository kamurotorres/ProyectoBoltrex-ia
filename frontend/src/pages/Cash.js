import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Banknote, Lock, Plus, Unlock, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getErrorMessage } from '@/lib/utils';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { money, shortDateTime as when } from '@/lib/format';
import { API, api } from '@/api/client';
import { AuthContext } from '@/auth/AuthProvider';
import CloseDialog from '@/features/cash/CloseDialog';
import SummaryTable, { Movements } from '@/features/cash/SessionParts';
import SessionDetailDialog from '@/features/cash/SessionDetailDialog';
import MovementDialog from '@/features/cash/MovementDialog';

// Control de caja (backlog P2.31): un turno por cajero con base inicial, movimientos (ventas
// de contado, abonos, reembolsos por devolución, ingresos y egresos manuales) y cierre con
// arqueo por denominaciones. Las reglas están en el backend (core/cash.py).

const DEFAULT_DENOMS = { bills: [100000, 50000, 20000, 10000, 5000, 2000], coins: [1000, 500, 200, 100, 50] };


const Cash = () => {
  const { user } = React.useContext(AuthContext);
  const { canCreate, canUpdate, isAdmin } = usePermissions();
  const [current, setCurrent] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState({ amount: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [movOpen, setMovOpen] = useState(false);
  const [mov, setMov] = useState({ kind: 'income', amount: '', reason: '' });
  const [closeTarget, setCloseTarget] = useState(null);
  const [detail, setDetail] = useState(null);
  const [filters, setFilters] = useState({ cashier: '', status: '' });
  const params = useMemo(() => Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), [filters]);
  const history = usePaginatedList(`${API}/cash/sessions`, { params, errorMessage: 'Error al cargar el historial de cajas' });

  const load = useCallback(async () => {
    try {
      const [cur, set] = await Promise.all([api.get(`/cash/current`), api.get(`/cash/settings`)]);
      setCurrent(cur.data);
      setSettings(set.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al cargar la caja'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); history.reload(); };

  const openCash = async () => {
    const amount = parseFloat(opening.amount);
    if (Number.isNaN(amount) || amount < 0) {
      toast.error('Escribe la base inicial en efectivo (puede ser 0).');
      return;
    }
    setBusy(true);
    try {
      const res = await api.post(`/cash/open`, { opening_amount: amount, notes: opening.notes || null });
      toast.success(`Caja ${res.data.session_id} abierta${res.data.attached_pending ? ` (se asociaron ${res.data.attached_pending} movimiento(s) pendientes)` : ''}.`);
      setOpening({ amount: '', notes: '' });
      refresh();
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo abrir la caja'));
    } finally {
      setBusy(false);
    }
  };

  const saveMovement = async () => {
    const amount = parseFloat(mov.amount);
    if (!(amount > 0)) { toast.error('El monto debe ser mayor a 0.'); return; }
    if (mov.reason.trim().length < 3) { toast.error('Escribe el motivo del movimiento (mínimo 3 caracteres).'); return; }
    setBusy(true);
    try {
      await api.post(`/cash/movements`, { kind: mov.kind, amount, reason: mov.reason.trim() });
      toast.success(mov.kind === 'income' ? 'Ingreso registrado' : 'Egreso registrado');
      setMovOpen(false);
      setMov({ kind: 'income', amount: '', reason: '' });
      load();
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo registrar el movimiento'));
    } finally {
      setBusy(false);
    }
  };

  const showDetail = async (sid) => {
    try {
      const res = await api.get(`/cash/sessions/${sid}`);
      setDetail(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cargar la caja'));
    }
  };

  if (loading) return <div className="text-center py-12">Cargando caja…</div>;
  const s = current?.session;
  const denoms = settings?.denominations || DEFAULT_DENOMS;

  return (
    <div className="space-y-6" data-testid="cash-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3"><Banknote className="h-8 w-8" />Caja</h1>
          <p className="text-muted-foreground mt-2">
            {settings?.require_open_session ? 'Se exige caja abierta para vender, recibir abonos y devolver efectivo.' : 'No se exige caja abierta para vender (lo configura el administrador en Config. Sistema).'}
          </p>
        </div>
      </div>

      {!s ? (
        <div className="bg-card border border-border rounded-lg p-5 space-y-4 max-w-xl" data-testid="cash-closed-card">
          <div>
            <h2 className="font-semibold flex items-center gap-2"><Lock className="h-4 w-4" />No tienes una caja abierta</h2>
            {current?.pending_movements > 0 && (
              <p className="text-sm text-amber-500 mt-1">Tienes {current.pending_movements} movimiento(s) registrados sin caja: se sumarán a la que abras.</p>
            )}
          </div>
          {canCreate('cash') ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Base inicial en efectivo *</Label>
                  <Input type="number" min="0" placeholder="Ej. 100000" value={opening.amount} onChange={(e) => setOpening((o) => ({ ...o, amount: e.target.value }))} data-testid="opening-amount" />
                </div>
                <div className="space-y-1">
                  <Label>Nota (opcional)</Label>
                  <Input value={opening.notes} maxLength={300} onChange={(e) => setOpening((o) => ({ ...o, notes: e.target.value }))} />
                </div>
              </div>
              <Button onClick={openCash} disabled={busy} data-testid="open-cash-button"><Unlock className="h-4 w-4 mr-2" />Abrir caja</Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Tu rol no tiene permiso para abrir caja.</p>
          )}
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg p-5 space-y-4" data-testid="cash-open-card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold flex items-center gap-2"><Unlock className="h-4 w-4 text-green-500" />Caja {s.session_id} abierta</h2>
              <p className="text-sm text-muted-foreground">{s.cashier_name} · desde {when(s.opened_at)} · base {money(s.opening_amount)}</p>
            </div>
            <div className="flex gap-2">
              {canCreate('cash') && <Button variant="outline" onClick={() => setMovOpen(true)} data-testid="add-cash-movement"><Plus className="h-4 w-4 mr-2" />Registrar movimiento</Button>}
              {canUpdate('cash') && <Button onClick={() => setCloseTarget(s)} data-testid="close-cash-button"><Lock className="h-4 w-4 mr-2" />Cerrar caja</Button>}
            </div>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">Efectivo que debería haber en la caja</p>
            <p className="text-3xl font-bold font-mono" data-testid="expected-cash">{money(s.summary.expected_cash)}</p>
          </div>
          <SummaryTable summary={s.summary} />
          <div>
            <h3 className="text-sm font-semibold mb-2">Movimientos del turno</h3>
            <Movements movements={s.movements} />
          </div>
        </div>
      )}

      {/* Historial */}
      <div className="bg-card border border-border rounded-lg p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Historial de cajas</h2>
          <div className="flex flex-wrap gap-2">
            {history.is_admin && (
              <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={filters.cashier}
                      onChange={(e) => setFilters((f) => ({ ...f, cashier: e.target.value }))} aria-label="Cajero">
                <option value="">Todos los cajeros</option>
                {(history.cashiers || []).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            )}
            <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={filters.status}
                    onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} aria-label="Estado">
              <option value="">Todas</option>
              <option value="open">Abiertas</option>
              <option value="closed">Cerradas</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="cash-history">
            <thead className="text-muted-foreground text-xs">
              <tr>
                <th className="text-left py-2 px-2 font-medium">Caja</th>
                {history.is_admin && <th className="text-left py-2 px-2 font-medium">Cajero</th>}
                <th className="text-left py-2 px-2 font-medium">Apertura</th>
                <th className="text-left py-2 px-2 font-medium">Cierre</th>
                <th className="text-right py-2 px-2 font-medium">Contado</th>
                <th className="text-right py-2 px-2 font-medium">Diferencia</th>
                <th className="text-left py-2 px-2 font-medium">Estado</th>
                <th className="py-2 px-2" aria-label="Acciones" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {history.items.map((h) => (
                <tr key={h.session_id}>
                  <td className="py-2 px-2 font-mono">{h.session_id}</td>
                  {history.is_admin && <td className="py-2 px-2">{h.cashier_email}</td>}
                  <td className="py-2 px-2 whitespace-nowrap">{when(h.opened_at)}</td>
                  <td className="py-2 px-2 whitespace-nowrap">{when(h.closed_at)}</td>
                  <td className="py-2 px-2 text-right font-mono">{h.status === 'closed' ? money(h.counted_cash) : '—'}</td>
                  <td className={`py-2 px-2 text-right font-mono ${!h.difference ? '' : h.difference > 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {h.status === 'closed' ? (h.difference ? `${h.difference > 0 ? '+' : '−'}${money(Math.abs(h.difference))}` : 'Cuadrada') : '—'}
                  </td>
                  <td className="py-2 px-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${h.status === 'open' ? 'bg-green-500/15 text-green-500' : 'bg-muted'}`}>
                      {h.status === 'open' ? 'Abierta' : h.forced_close ? 'Cerrada (forzado)' : 'Cerrada'}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-right">
                    <Button size="sm" variant="ghost" onClick={() => showDetail(h.session_id)} aria-label={`Ver caja ${h.session_id}`}><Eye className="h-4 w-4" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {history.items.length === 0 && !history.loading && <p className="text-sm text-muted-foreground py-6 text-center">Sin cajas registradas.</p>}
        </div>
        <Pagination {...history.paginationProps} noun="caja(s)" testId="cash-pagination" />
      </div>

      {/* Movimiento manual */}
      <MovementDialog busy={busy} mov={mov} movOpen={movOpen} saveMovement={saveMovement} setMov={setMov} setMovOpen={setMovOpen} />

      {/* Detalle de una caja del historial */}
      <SessionDetailDialog canUpdate={canUpdate} detail={detail} isAdmin={isAdmin} setCloseTarget={setCloseTarget} setDetail={setDetail} user={user} />

      <CloseDialog
        open={!!closeTarget}
        onOpenChange={(o) => !o && setCloseTarget(null)}
        cashSession={closeTarget}
        denoms={denoms}
        forced={!!closeTarget && closeTarget.cashier_email !== user?.email}
        onClosed={(closed) => { setCloseTarget(null); refresh(); setDetail(closed); }}
      />
    </div>
  );
};

export default Cash;
