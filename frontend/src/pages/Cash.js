import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Banknote, Lock, Plus, Printer, Unlock, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { getErrorMessage } from '@/lib/utils';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import ExportMenu from '@/components/ExportMenu';
import { money, shortDateTime as when } from '@/lib/format';
import { API, api } from '@/api/client';
import { AuthContext } from '@/auth/AuthProvider';

// Control de caja (backlog P2.31): un turno por cajero con base inicial, movimientos (ventas
// de contado, abonos, reembolsos por devolución, ingresos y egresos manuales) y cierre con
// arqueo por denominaciones. Las reglas están en el backend (core/cash.py).

const DEFAULT_DENOMS = { bills: [100000, 50000, 20000, 10000, 5000, 2000], coins: [1000, 500, 200, 100, 50] };

function SummaryTable({ summary }) {
  if (!summary) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="cash-summary">
        <thead className="text-muted-foreground text-xs">
          <tr>
            <th className="text-left py-2 px-2 font-medium">Forma de pago</th>
            <th className="text-right py-2 px-2 font-medium">Base</th>
            <th className="text-right py-2 px-2 font-medium">Ventas</th>
            <th className="text-right py-2 px-2 font-medium">Abonos</th>
            <th className="text-right py-2 px-2 font-medium">Reembolsos</th>
            <th className="text-right py-2 px-2 font-medium">Ingresos</th>
            <th className="text-right py-2 px-2 font-medium">Egresos</th>
            <th className="text-right py-2 px-2 font-medium">Esperado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border font-mono">
          {summary.methods.map((m) => (
            <tr key={m.method} className={m.is_cash ? 'font-semibold' : ''}>
              <td className="py-2 px-2 font-sans">{m.method}</td>
              <td className="py-2 px-2 text-right">{m.is_cash ? money(m.opening) : '—'}</td>
              <td className="py-2 px-2 text-right">{money(m.sales)}</td>
              <td className="py-2 px-2 text-right">{money(m.fio_payments)}</td>
              <td className="py-2 px-2 text-right">{m.refunds ? `−${money(m.refunds)}` : money(0)}</td>
              <td className="py-2 px-2 text-right">{money(m.income)}</td>
              <td className="py-2 px-2 text-right">{m.expense ? `−${money(m.expense)}` : money(0)}</td>
              <td className="py-2 px-2 text-right">{money(m.expected)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground mt-2">
        Efectivo esperado = base + ventas + abonos + ingresos − reembolsos − egresos (solo efectivo).
      </p>
    </div>
  );
}

function Movements({ movements }) {
  if (!movements?.length) return <p className="text-sm text-muted-foreground py-4">Sin movimientos todavía.</p>;
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="text-left py-1.5 px-2 font-medium">Hora</th>
            <th className="text-left py-1.5 px-2 font-medium">Tipo</th>
            <th className="text-left py-1.5 px-2 font-medium">Forma de pago</th>
            <th className="text-left py-1.5 px-2 font-medium">Referencia / motivo</th>
            <th className="text-right py-1.5 px-2 font-medium">Monto</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {movements.map((m, i) => (
            <tr key={i}>
              <td className="py-1.5 px-2 whitespace-nowrap">{when(m.created_at)}</td>
              <td className="py-1.5 px-2">{m.kind_label}{m.attached_on_open ? ' (pendiente)' : ''}</td>
              <td className="py-1.5 px-2">{m.method}</td>
              <td className="py-1.5 px-2">{m.reference || m.reason || '—'}</td>
              <td className="py-1.5 px-2 text-right font-mono">{m.direction === 'out' ? '−' : '+'}{money(m.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Reporte de cierre imprimible en ticket de 80 mm.
function printReport(s) {
  const rows = (s.summary?.methods || []).map((m) => `<tr><td>${m.method}</td><td class="r">${money(m.expected)}</td></tr>`).join('');
  const denoms = Object.entries(s.denominations || {}).sort((a, b) => b[0] - a[0])
    .map(([d, q]) => `<tr><td>${q} × ${money(d)}</td><td class="r">${money(d * q)}</td></tr>`).join('');
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Cierre ${s.session_id}</title>
  <style>@page{size:80mm auto;margin:4mm}body{font:12px monospace;width:72mm;margin:0}h1{font-size:14px;text-align:center;margin:0 0 6px}
  table{width:100%;border-collapse:collapse}td{padding:2px 0}.r{text-align:right}hr{border:0;border-top:1px dashed #000;margin:6px 0}</style></head><body>
  <h1>CIERRE DE CAJA ${s.session_id}</h1>
  <div>Cajero: ${s.cashier_name || s.cashier_email}</div><div>Apertura: ${when(s.opened_at)}</div><div>Cierre: ${when(s.closed_at)}</div>
  ${s.forced_close ? `<div>Cerrada por: ${s.closed_by} (forzado)</div>` : ''}<hr>
  <div><b>Esperado por forma de pago</b></div><table>${rows}</table><hr>
  <table><tr><td>Base inicial</td><td class="r">${money(s.opening_amount)}</td></tr>
  <tr><td>Efectivo esperado</td><td class="r">${money(s.summary?.expected_cash)}</td></tr>
  <tr><td>Efectivo contado</td><td class="r">${money(s.counted_cash)}</td></tr>
  <tr><td><b>Diferencia</b></td><td class="r"><b>${s.difference > 0 ? '+' : ''}${money(s.difference)}</b></td></tr></table>
  ${denoms ? `<hr><div><b>Arqueo</b></div><table>${denoms}</table>` : ''}
  ${s.closing_notes ? `<hr><div>Obs.: ${s.closing_notes}</div>` : ''}
  <hr><div style="text-align:center">Firma cajero: ____________</div></body></html>`;
  const w = window.open('', '_blank', 'width=420,height=640');
  if (!w) {
    toast.error('El navegador bloqueó la ventana de impresión: permite las ventanas emergentes para Boltrex.');
    return;
  }
  w.document.write(html);
  w.document.close();
  w.focus();
  w.print();
}

function CloseDialog({ open, onOpenChange, cashSession, denoms, forced, onClosed }) {
  const [mode, setMode] = useState('denominations');
  const [qty, setQty] = useState({});
  const [total, setTotal] = useState('');
  const [notes, setNotes] = useState('');
  const [reconciled, setReconciled] = useState({});
  const [saving, setSaving] = useState(false);
  const expected = cashSession?.summary?.expected_cash || 0;
  const all = [...denoms.bills, ...denoms.coins];
  const counted = mode === 'denominations'
    ? all.reduce((sum, d) => sum + d * (parseInt(qty[d], 10) || 0), 0)
    : parseFloat(total) || 0;
  const diff = Math.round((counted - expected) * 100) / 100;
  const others = (cashSession?.summary?.methods || []).filter((m) => !m.is_cash && m.expected);

  useEffect(() => {
    if (open) { setQty({}); setTotal(''); setNotes(''); setReconciled({}); setMode('denominations'); }
  }, [open]);

  const submit = async () => {
    if (diff !== 0 && !notes.trim()) {
      toast.error(`Hay ${diff > 0 ? 'un sobrante' : 'un faltante'} de ${money(Math.abs(diff))}: escribe una observación para cerrar.`);
      return;
    }
    if (forced && !notes.trim()) {
      toast.error('Para cerrar la caja de otro cajero escribe el motivo en observaciones.');
      return;
    }
    setSaving(true);
    try {
      const body = { notes, reconciled };
      if (mode === 'denominations') {
        body.denominations = Object.fromEntries(all.filter((d) => parseInt(qty[d], 10) > 0).map((d) => [String(d), parseInt(qty[d], 10)]));
        if (!Object.keys(body.denominations).length) body.counted_cash = 0;
      } else {
        body.counted_cash = counted;
      }
      const res = await api.post(`/cash/sessions/${cashSession.session_id}/close`, body);
      toast.success(`Caja ${cashSession.session_id} cerrada${res.data.difference ? ` con ${res.data.difference > 0 ? 'sobrante' : 'faltante'} de ${money(Math.abs(res.data.difference))}` : ' cuadrada'}.`);
      onClosed(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cerrar la caja'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="close-cash-dialog">
        <DialogHeader>
          <DialogTitle>Cerrar caja {cashSession?.session_id}{forced ? ` de ${cashSession?.cashier_email}` : ''}</DialogTitle>
          <DialogDescription>Cuenta el efectivo y compáralo con lo que debería haber.</DialogDescription>
        </DialogHeader>
        <div className="flex gap-1">
          <Button size="sm" variant={mode === 'denominations' ? 'default' : 'outline'} onClick={() => setMode('denominations')}>Por billetes y monedas</Button>
          <Button size="sm" variant={mode === 'total' ? 'default' : 'outline'} onClick={() => setMode('total')}>Solo el total</Button>
        </div>
        {mode === 'denominations' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {all.map((d) => (
              <label key={d} className="flex items-center gap-2 text-sm">
                <span className="w-20 text-right font-mono">{money(d)}</span>
                <span className="text-muted-foreground">×</span>
                <Input type="number" min="0" step="1" className="h-8" value={qty[d] ?? ''} onChange={(e) => setQty((q) => ({ ...q, [d]: e.target.value }))}
                       aria-label={`Cantidad de ${money(d)}`} data-testid={`denom-${d}`} />
              </label>
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            <Label>Efectivo contado</Label>
            <Input type="number" min="0" value={total} onChange={(e) => setTotal(e.target.value)} data-testid="counted-total" />
          </div>
        )}
        <div className="grid grid-cols-3 gap-2 rounded-md border border-border p-3 text-sm">
          <div><p className="text-xs text-muted-foreground">Esperado</p><p className="font-mono font-semibold">{money(expected)}</p></div>
          <div><p className="text-xs text-muted-foreground">Contado</p><p className="font-mono font-semibold">{money(counted)}</p></div>
          <div>
            <p className="text-xs text-muted-foreground">Diferencia</p>
            <p className={`font-mono font-semibold ${diff === 0 ? '' : diff > 0 ? 'text-green-500' : 'text-red-500'}`} data-testid="close-diff">
              {diff === 0 ? 'Cuadrada ✓' : `${diff > 0 ? 'Sobrante +' : 'Faltante −'}${money(Math.abs(diff))}`}
            </p>
          </div>
        </div>
        {others.length > 0 && (
          <div className="space-y-1">
            <p className="text-sm font-medium">Otras formas de pago (verifica con los comprobantes)</p>
            {others.map((m) => (
              <label key={m.method} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!reconciled[m.method]} onChange={(e) => setReconciled((r) => ({ ...r, [m.method]: e.target.checked }))} />
                {m.method}: <span className="font-mono">{money(m.expected)}</span> conciliado
              </label>
            ))}
          </div>
        )}
        <div className="space-y-1">
          <Label>Observaciones {diff !== 0 || forced ? '*' : '(opcional)'}</Label>
          <Input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500}
                 placeholder={forced ? 'Motivo del cierre forzado' : diff !== 0 ? 'Explica la diferencia' : ''} data-testid="close-notes" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={submit} disabled={saving} data-testid="confirm-close-cash"><Lock className="h-4 w-4 mr-2" />{saving ? 'Cerrando…' : 'Cerrar caja'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

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
      <Dialog open={movOpen} onOpenChange={setMovOpen}>
        <DialogContent data-testid="cash-movement-dialog">
          <DialogHeader>
            <DialogTitle>Registrar movimiento de efectivo</DialogTitle>
            <DialogDescription>Ingreso (p. ej. más sencillo) o egreso (gasto, pago, retiro a la caja fuerte).</DialogDescription>
          </DialogHeader>
          <div className="flex gap-1">
            <Button size="sm" variant={mov.kind === 'income' ? 'default' : 'outline'} onClick={() => setMov((m) => ({ ...m, kind: 'income' }))}>Ingreso</Button>
            <Button size="sm" variant={mov.kind === 'expense' ? 'default' : 'outline'} onClick={() => setMov((m) => ({ ...m, kind: 'expense' }))}>Egreso</Button>
          </div>
          <div className="space-y-1"><Label>Monto *</Label><Input type="number" min="0" value={mov.amount} onChange={(e) => setMov((m) => ({ ...m, amount: e.target.value }))} /></div>
          <div className="space-y-1"><Label>Motivo *</Label><Input value={mov.reason} maxLength={200} onChange={(e) => setMov((m) => ({ ...m, reason: e.target.value }))} /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMovOpen(false)}>Cancelar</Button>
            <Button onClick={saveMovement} disabled={busy}>Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detalle de una caja del historial */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="cash-detail-dialog">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle>Caja {detail.session_id} · {detail.status === 'open' ? 'abierta' : 'cerrada'}</DialogTitle>
                <DialogDescription>
                  {detail.cashier_name} ({detail.cashier_email}) · apertura {when(detail.opened_at)}
                  {detail.closed_at ? ` · cierre ${when(detail.closed_at)}${detail.forced_close ? ` por ${detail.closed_by} (forzado)` : ''}` : ''}
                </DialogDescription>
              </DialogHeader>
              {detail.status === 'closed' && (
                <div className="grid grid-cols-3 gap-2 rounded-md border border-border p-3 text-sm">
                  <div><p className="text-xs text-muted-foreground">Esperado</p><p className="font-mono">{money(detail.summary?.expected_cash)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Contado</p><p className="font-mono">{money(detail.counted_cash)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Diferencia</p><p className="font-mono">{detail.difference ? `${detail.difference > 0 ? '+' : '−'}${money(Math.abs(detail.difference))}` : 'Cuadrada'}</p></div>
                  {detail.closing_notes && <p className="col-span-3 text-xs text-muted-foreground">Observaciones: {detail.closing_notes}</p>}
                </div>
              )}
              <SummaryTable summary={detail.summary} />
              <Movements movements={detail.movements} />
              <DialogFooter>
                {detail.status === 'closed' && <Button variant="outline" onClick={() => printReport(detail)}><Printer className="h-4 w-4 mr-2" />Imprimir cierre</Button>}
                {/* P2.33: cierre en PDF A4 (movimientos, por forma de pago y arqueo) o Excel */}
                <ExportMenu url={`${API}/cash/sessions/${detail.session_id}/export`} formats={['pdf', 'xlsx']} label="Descargar"
                            fallbackName={`caja_${detail.session_id}`} testId="cash-export-button" />
                {detail.status === 'open' && isAdmin && detail.cashier_email !== user?.email && canUpdate('cash') && (
                  <Button onClick={() => { setCloseTarget(detail); setDetail(null); }} data-testid="force-close-button"><Lock className="h-4 w-4 mr-2" />Cerrar (forzado)</Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

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
