import React, { useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ScrollText,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Monitor,
  Smartphone,
  Tablet,
  Code,
  HelpCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import { API, AuthContext } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getErrorMessage } from '@/lib/utils';

// Bitácora de auditoría (backlog P1.12). Solo lectura y solo para el rol Administrador:
// el backend lo exige (403 con mensaje) y el menú solo la muestra a administradores.

const PAGE_SIZE = 50;
const EMPTY_FILTERS = { date_from: '', date_to: '', actor: '', module: '', action: '', device: '', success: '', q: '' };

const selectClass =
  'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring';

const formatDate = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('es-CO', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const formatValue = (v) => {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

const DeviceIcon = ({ device }) => {
  const d = (device || '').toLowerCase();
  const cls = 'h-4 w-4 shrink-0 text-muted-foreground';
  if (d.startsWith('celular')) return <Smartphone className={cls} />;
  if (d.startsWith('tablet')) return <Tablet className={cls} />;
  if (d.startsWith('pc')) return <Monitor className={cls} />;
  if (d.startsWith('otro')) return <Code className={cls} />;
  return <HelpCircle className={cls} />;
};

const AuditDetail = ({ item }) => (
  <div className="space-y-3 text-sm">
    {item.changes && item.changes.length > 0 ? (
      <div className="overflow-x-auto">
        <table className="w-full text-xs border border-border rounded">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Campo</th>
              <th className="px-3 py-2 text-left font-medium">Antes</th>
              <th className="px-3 py-2 text-left font-medium">Después</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {item.changes.map((c) => (
              <tr key={c.field}>
                <td className="px-3 py-1.5">
                  {c.label || c.field}
                  {c.label && c.label !== c.field && <span className="block font-mono text-[10px] text-muted-foreground">{c.field}</span>}
                </td>
                <td className="px-3 py-1.5 text-red-600 dark:text-red-400 break-all">{formatValue(c.before)}</td>
                <td className="px-3 py-1.5 text-green-700 dark:text-green-400 break-all">{formatValue(c.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <p className="text-muted-foreground text-xs">Sin cambios campo por campo para esta acción.</p>
    )}
    {item.details && (
      <details>
        <summary className="cursor-pointer text-xs text-muted-foreground">Datos adicionales</summary>
        <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted/50 p-2 text-[11px]">{JSON.stringify(item.details, null, 2)}</pre>
      </details>
    )}
    <p className="text-[11px] text-muted-foreground break-all">
      <span className="font-medium">Navegador completo (User-Agent):</span> {item.user_agent || '—'}
    </p>
  </div>
);

const Audit = () => {
  const { user } = useContext(AuthContext);
  const isAdmin = (user?.roles || []).includes('Administrador');

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [options, setOptions] = useState({ actors: [], modules: [], actions: [], devices: [], retention_days: null });
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE, tz_offset_minutes: new Date().getTimezoneOffset() };
      Object.entries(applied).forEach(([k, v]) => {
        if (v !== '') params[k] = v;
      });
      const res = await axios.get(`${API}/audit`, { params });
      setData(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudo cargar la auditoría'));
    } finally {
      setLoading(false);
    }
  }, [page, applied]);

  useEffect(() => {
    if (!isAdmin) return;
    axios
      .get(`${API}/audit/filters`)
      .then((res) => setOptions(res.data))
      .catch((error) => toast.error(getErrorMessage(error, 'No se pudieron cargar los filtros')));
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin, load]);

  if (!isAdmin) {
    return (
      <div className="bg-card border border-border rounded-lg p-6" data-testid="audit-forbidden">
        <p className="font-semibold">Solo los administradores pueden ver la auditoría del sistema.</p>
      </div>
    );
  }

  const change = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const apply = (e) => {
    e?.preventDefault();
    if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) {
      toast.error("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.");
      return;
    }
    setExpanded(null);
    setPage(1);
    setApplied(filters);
  };
  const clear = () => {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(1);
  };

  const retention = options.retention_days;

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ScrollText className="h-6 w-6" />
            Auditoría
          </h1>
          <p className="text-muted-foreground mt-1">
            Quién hizo qué, cuándo y desde dónde.{' '}
            {retention ? `Se conservan los últimos ${retention} días.` : retention === 0 ? 'Se conserva todo el historial.' : ''}
          </p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading} data-testid="audit-refresh">
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Actualizar
        </Button>
      </div>

      <form onSubmit={apply} className="bg-card border border-border rounded-lg p-4 space-y-4" data-testid="audit-filters">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8 gap-3">
          <div className="space-y-1">
            <Label>Desde</Label>
            <Input type="date" value={filters.date_from} onChange={(e) => change('date_from', e.target.value)} data-testid="audit-date-from" />
          </div>
          <div className="space-y-1">
            <Label>Hasta</Label>
            <Input type="date" value={filters.date_to} onChange={(e) => change('date_to', e.target.value)} data-testid="audit-date-to" />
          </div>
          <div className="space-y-1">
            <Label>Usuario</Label>
            <select className={selectClass} value={filters.actor} onChange={(e) => change('actor', e.target.value)} data-testid="audit-actor">
              <option value="">Todos</option>
              {options.actors.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Módulo</Label>
            <select className={selectClass} value={filters.module} onChange={(e) => change('module', e.target.value)} data-testid="audit-module">
              <option value="">Todos</option>
              {options.modules.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Acción</Label>
            <select className={selectClass} value={filters.action} onChange={(e) => change('action', e.target.value)} data-testid="audit-action">
              <option value="">Todas</option>
              {options.actions.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Dispositivo</Label>
            <select className={selectClass} value={filters.device} onChange={(e) => change('device', e.target.value)} data-testid="audit-device">
              <option value="">Todos</option>
              {options.devices.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Resultado</Label>
            <select className={selectClass} value={filters.success} onChange={(e) => change('success', e.target.value)} data-testid="audit-success">
              <option value="">Todos</option>
              <option value="true">Correcto</option>
              <option value="false">Fallido / rechazado</option>
            </select>
          </div>
          <div className="space-y-1">
            <Label>Buscar</Label>
            <Input placeholder="Código, factura, nombre, IP…" value={filters.q} onChange={(e) => change('q', e.target.value)} data-testid="audit-search" />
          </div>
        </div>
        <div className="flex gap-2">
          <Button type="submit" size="sm" data-testid="audit-apply">
            <Search className="h-4 w-4 mr-2" />
            Filtrar
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={clear} data-testid="audit-clear">
            <X className="h-4 w-4 mr-2" />
            Limpiar
          </Button>
        </div>
      </form>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="audit-table">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-3 w-8" aria-label="Detalle" />
                <th className="px-3 py-3 text-left font-medium whitespace-nowrap">Fecha y hora</th>
                <th className="px-3 py-3 text-left font-medium">Usuario</th>
                <th className="px-3 py-3 text-left font-medium">Módulo</th>
                <th className="px-3 py-3 text-left font-medium">Acción</th>
                <th className="px-3 py-3 text-left font-medium">Registro</th>
                <th className="px-3 py-3 text-left font-medium min-w-[260px]">Resumen</th>
                <th className="px-3 py-3 text-left font-medium">Navegador</th>
                <th className="px-3 py-3 text-left font-medium">Dispositivo</th>
                <th className="px-3 py-3 text-left font-medium">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading && data.items.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">Cargando…</td></tr>
              ) : data.items.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">No hay registros con esos filtros.</td></tr>
              ) : (
                data.items.map((item, idx) => {
                  const key = `${item.at}-${idx}`;
                  const open = expanded === key;
                  return (
                    <React.Fragment key={key}>
                      <tr
                        className={`cursor-pointer hover:bg-muted/30 ${item.success === false ? 'bg-red-500/5' : ''}`}
                        onClick={() => setExpanded(open ? null : key)}
                        data-testid="audit-row"
                      >
                        <td className="px-3 py-2 text-muted-foreground">
                          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">{formatDate(item.at)}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{item.actor_email}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{item.module_label}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${item.success === false ? 'bg-red-500/15 text-red-700 dark:text-red-300' : 'bg-muted'}`}>
                            {item.action_label}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="font-mono text-xs">{item.entity_id}</div>
                          {item.entity_name && item.entity_name !== item.entity_id && (
                            <div className="text-xs text-muted-foreground">{item.entity_name}</div>
                          )}
                        </td>
                        <td className="px-3 py-2">{item.summary}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{item.browser}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span className="flex items-center gap-1.5"><DeviceIcon device={item.device} />{item.device}</span>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">{item.ip || '—'}</td>
                      </tr>
                      {open && (
                        <tr className="bg-muted/20">
                          <td />
                          <td colSpan={9} className="px-3 py-3"><AuditDetail item={item} /></td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-sm">
          <span className="text-muted-foreground">
            {data.total} registro(s) · página {data.page} de {data.pages}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)} data-testid="audit-prev">
              <ChevronLeft className="h-4 w-4 mr-1" /> Anterior
            </Button>
            <Button size="sm" variant="outline" disabled={page >= data.pages || loading} onClick={() => setPage((p) => p + 1)} data-testid="audit-next">
              Siguiente <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Audit;
