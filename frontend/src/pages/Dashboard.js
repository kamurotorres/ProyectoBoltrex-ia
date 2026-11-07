import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Minus, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getErrorMessage } from '@/lib/utils';
import { usePermissions } from '@/hooks/usePermissions';
import { BarList, ChartCard, ColumnChart, DataTable, money } from '@/components/charts/Charts';
import { api } from '@/api/client';
import { localYmd, number } from '@/lib/format';

// Dashboard (backlog P2.29). Un vendedor ve solo sus ventas; el Administrador ve toda la
// tienda y puede filtrar por vendedor. Las cifras usan las mismas reglas que Reportes
// (ventas netas por fecha de la venta, días locales). Ganancia = (precio de venta sin IVA −
// precio de compra) × cantidad, con el costo guardado en cada venta.

const localDate = localYmd; // AAAA-MM-DD en hora local (lib/format)
const PERIODS = [
  { key: 'today', label: 'Hoy' },
  { key: '7d', label: '7 días' },
  { key: '30d', label: '30 días' },
  { key: 'month', label: 'Este mes' },
  { key: 'custom', label: 'Rango' },
];

function rangeFor(key) {
  const now = new Date();
  const end = localDate(now);
  if (key === '7d' || key === '30d') {
    const d = new Date(now);
    d.setDate(d.getDate() - (key === '7d' ? 6 : 29));
    return { start: localDate(d), end };
  }
  if (key === 'month') return { start: localDate(new Date(now.getFullYear(), now.getMonth(), 1)), end };
  return { start: end, end };
}

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const bucketLabel = (iso, bucket) => {
  const [y, m, d] = iso.split('-').map(Number);
  if (bucket === 'month') return `${MONTHS[m - 1]} ${String(y).slice(2)}`;
  return `${d} ${MONTHS[m - 1]}`;
};
const BUCKET_NAME = { day: 'día', week: 'semana', month: 'mes' };

function Delta({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-muted-foreground">sin periodo anterior para comparar</span>;
  }
  const up = value > 0;
  const flat = value === 0;
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  const cls = flat ? 'text-muted-foreground' : up ? 'text-green-500' : 'text-red-500';
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs ${cls}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {up ? '+' : ''}{number(value)} %
      <span className="text-muted-foreground ml-1">vs. periodo anterior</span>
    </span>
  );
}

function Kpi({ title, value, delta, note, testId }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4" data-testid={testId}>
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <p className="text-2xl font-bold font-mono mt-1">{value}</p>
      <div className="mt-1 min-h-[1rem]">{delta !== undefined ? <Delta value={delta} /> : null}</div>
      {note && <p className="text-[11px] text-muted-foreground mt-1">{note}</p>}
    </div>
  );
}

const Dashboard = () => {
  const { canRead } = usePermissions();
  const [period, setPeriod] = useState('today');
  const [custom, setCustom] = useState(rangeFor('today'));
  const [seller, setSeller] = useState('');
  const [topBy, setTopBy] = useState('net');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const range = period === 'custom' ? custom : rangeFor(period);

  const load = useCallback(async () => {
    if (range.start > range.end) {
      toast.error("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.");
      return;
    }
    setLoading(true);
    try {
      const params = { start_date: range.start, end_date: range.end, tz_offset_minutes: new Date().getTimezoneOffset() };
      if (seller) params.seller = seller;
      const res = await api.get(`/dashboard/summary`, { params });
      setData(res.data);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al cargar el dashboard'));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.start, range.end, seller]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !data) return <div className="text-center py-12">Cargando dashboard…</div>;
  if (!data) return null;

  const k = data.kpis;
  const c = data.comparison;
  const bucket = data.range.bucket;
  const series = data.series.map((s) => ({ ...s, label: bucketLabel(s.date, bucket) }));
  const hours = data.hours.map((h) => ({ ...h, label: `${h.hour}h` }));
  const top = data.top_products[topBy === 'net' ? 'by_net' : 'by_units'];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">
          {data.scope.is_admin
            ? data.scope.seller ? `Ventas de ${data.scope.seller}` : 'Toda la tienda'
            : 'Tus ventas'}
          {' · '}{range.start === range.end ? range.start : `${range.start} a ${range.end}`}
        </p>
      </div>

      {/* Filtros en una sola fila */}
      <div className="flex flex-wrap items-end gap-2" data-testid="dashboard-filters">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Periodo">
          {PERIODS.map((p) => (
            <Button key={p.key} size="sm" variant={period === p.key ? 'default' : 'outline'} onClick={() => setPeriod(p.key)}
                    aria-pressed={period === p.key} data-testid={`period-${p.key}`}>
              {p.label}
            </Button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex items-center gap-1">
            <Input type="date" className="h-9 w-[150px]" value={custom.start} onChange={(e) => setCustom((r) => ({ ...r, start: e.target.value }))} aria-label="Desde" />
            <span className="text-muted-foreground text-sm">a</span>
            <Input type="date" className="h-9 w-[150px]" value={custom.end} onChange={(e) => setCustom((r) => ({ ...r, end: e.target.value }))} aria-label="Hasta" />
          </div>
        )}
        {data.scope.is_admin && (
          <select
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
            value={seller}
            onChange={(e) => setSeller(e.target.value)}
            aria-label="Vendedor"
            data-testid="dashboard-seller"
          >
            <option value="">Todos los vendedores</option>
            {(data.sellers || []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <Button size="sm" variant="ghost" onClick={load} disabled={loading} aria-label="Actualizar">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        <Kpi title="Ventas netas" value={money(k.net_sales)} delta={c.net_sales} testId="kpi-net-sales"
             note={k.returns_total ? `Devoluciones: −${money(k.returns_total)}` : null} />
        <Kpi title="Facturas" value={number(k.invoices)} delta={c.invoices} testId="kpi-invoices" />
        <Kpi title="Ticket promedio" value={money(k.avg_ticket)} delta={c.avg_ticket} testId="kpi-avg-ticket" />
        <Kpi title="Unidades vendidas" value={number(k.units)} delta={c.units} testId="kpi-units" />
        <Kpi title="Ganancia bruta" value={money(k.profit)} delta={c.profit} testId="kpi-profit"
             note={k.invoices_without_cost ? `${k.invoices_without_cost} venta(s) antiguas sin costo registrado no se incluyen` : 'Precio de venta (sin IVA) − precio de compra'} />
        <Kpi title="Cartera Fios" value={money(data.credit.balance)} testId="kpi-credit"
             note={`${data.credit.clients} cliente(s) con saldo pendiente`} />
        {/* P2.30: lo vencido y lo que vence pronto (no depende del periodo) */}
        <Kpi title="Cartera vencida" value={money(data.credit.overdue_balance || 0)} testId="kpi-credit-overdue"
             note={data.credit.overdue_balance
               ? `${data.credit.overdue_invoices} factura(s) de ${data.credit.overdue_clients} cliente(s) · por vencer (${data.credit.due_soon_days} días): ${money(data.credit.due_soon_balance || 0)}`
               : `Nada vencido · por vencer (${data.credit.due_soon_days ?? 5} días): ${money(data.credit.due_soon_balance || 0)}`} />
      </div>

      {/* Gráficas */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <ChartCard
            title={`Ventas netas por ${BUCKET_NAME[bucket]}`}
            subtitle="Pasa el mouse sobre una barra para ver el detalle"
            testId="chart-series"
            table={<DataTable columns={[{ key: 'label', label: BUCKET_NAME[bucket] }, { key: 'invoices', label: 'Facturas', align: 'right' },
                                        { key: 'net', label: 'Ventas netas', align: 'right', format: money }]} rows={series} />}
          >
            <ColumnChart
              data={series}
              labelEvery={Math.ceil(series.length / 12)}
              ariaLabel={`Ventas netas por ${BUCKET_NAME[bucket]}, ${series.length} barras`}
              tooltip={(d) => [d.label, `Ventas netas: ${money(d.net)}`, `${d.invoices} factura(s)`]}
            />
          </ChartCard>
        </div>
        <ChartCard
          title="Formas de pago"
          subtitle="Ventas netas del periodo"
          testId="chart-payments"
          table={<DataTable columns={[{ key: 'method', label: 'Forma de pago' }, { key: 'invoices', label: 'Facturas', align: 'right' },
                                      { key: 'net', label: 'Ventas', align: 'right', format: money }, { key: 'share', label: '%', align: 'right', format: (v) => `${v} %` }]}
                             rows={data.payments} />}
        >
          <BarList
            items={data.payments}
            value={(p) => p.net}
            label={(p) => p.method}
            detail={(p) => `${money(p.net)} · ${number(p.share)} %`}
            ariaLabel="Ventas por forma de pago"
          />
        </ChartCard>

        <div className="xl:col-span-2">
          <ChartCard
            title="Ventas por hora del día"
            subtitle="Hora local · para ver en qué horas hay más clientes"
            testId="chart-hours"
            table={<DataTable columns={[{ key: 'label', label: 'Hora' }, { key: 'invoices', label: 'Facturas', align: 'right' },
                                        { key: 'net', label: 'Ventas netas', align: 'right', format: money }]}
                               rows={hours.filter((h) => h.invoices)} />}
          >
            <ColumnChart
              data={hours}
              labelEvery={3}
              height={180}
              ariaLabel="Ventas netas por hora del día"
              tooltip={(d) => [`${d.hour}:00 – ${d.hour}:59`, `Ventas netas: ${money(d.net)}`, `${d.invoices} factura(s)`]}
            />
          </ChartCard>
        </div>
        <ChartCard
          title="Top 10 productos"
          subtitle={topBy === 'net' ? 'Por ventas netas' : 'Por unidades vendidas'}
          testId="chart-top"
          table={<DataTable columns={[{ key: 'name', label: 'Producto' }, { key: 'units', label: 'Unidades', align: 'right' },
                                      { key: 'net', label: 'Ventas netas', align: 'right', format: money }]} rows={top} />}
        >
          <div className="flex gap-1 mb-3" role="group" aria-label="Ordenar top por">
            <Button size="sm" variant={topBy === 'net' ? 'default' : 'outline'} className="h-7 text-xs" onClick={() => setTopBy('net')}>Por $</Button>
            <Button size="sm" variant={topBy === 'units' ? 'default' : 'outline'} className="h-7 text-xs" onClick={() => setTopBy('units')}>Por unidades</Button>
          </div>
          <BarList
            items={top}
            value={(p) => (topBy === 'net' ? p.net : p.units)}
            label={(p) => p.name}
            detail={(p) => (topBy === 'net' ? `${money(p.net)} · ${p.units} u` : `${p.units} u · ${money(p.net)}`)}
            ariaLabel="Top 10 productos"
          />
        </ChartCard>
      </div>

      {/* Alertas */}
      {(data.stock.low_stock_count > 0 || data.stock.out_of_stock_count > 0) && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm" role="status" data-testid="stock-alert">
          <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-semibold">Atención:</span> {data.stock.low_stock_count} producto(s) con bajo stock (bajo su mínimo; general {data.stock.threshold} unidades)
            {data.stock.out_of_stock_count > 0 && `, de ellos ${data.stock.out_of_stock_count} agotado(s)`}.
          </span>
          {canRead('inventory') && (
            <Link to="/inventory" className="underline underline-offset-2 hover:text-foreground">Ver inventario</Link>
          )}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
