import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Eye, Loader2, Plus, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import ExportMenu from '@/components/ExportMenu';
import { notifyDataChanged } from '@/lib/events';
import { money, signedMoney } from '@/lib/format';
import { API, api } from '@/api/client';
import { useServerSearch } from '@/hooks/useServerSearch';

export { signedMoney };   // Inventario lo importa desde aquí

// P2.32: ajustes de inventario (entrada / salida / conteo físico). Un ajuste no se edita ni se borra.
export const KIND_LABELS = { entrada: 'Entrada', salida: 'Salida', conteo: 'Conteo físico' };
const KIND_HELP = {
  entrada: 'Suma unidades al stock (inventario inicial, sobrante, corrección).',
  salida: 'Resta unidades del stock (merma, daño, vencido, consumo interno…). Nunca deja el stock negativo.',
  conteo: 'Escribe lo que contaste: el sistema calcula la diferencia y deja el stock en lo contado.',
};
const tz = () => new Date().getTimezoneOffset();

// ------------------------------------------------------------------ formulario de nuevo ajuste

export const AdjustmentDialog = ({ open, onOpenChange, initialProduct, onSaved }) => {
  const [kind, setKind] = useState('salida');
  const [reasons, setReasons] = useState([]);
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState([]);       // { barcode, name, stock, cost, value }
  const [search, setSearch] = useState('');
  // Búsqueda de productos en el servidor (desde 2 caracteres) con el hook compartido (fase 5).
  const { results } = useServerSearch('/inventory', search, { pageSize: 10, errorMessage: 'Error al buscar productos' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setKind('salida');
    setNotes('');
    setSearch('');
    setItems(initialProduct ? [{ barcode: initialProduct.barcode, name: initialProduct.name, stock: initialProduct.stock,
                                 cost: initialProduct.purchase_price || 0, value: '' }] : []);
    api.get(`/adjustment-reasons`, { params: { active_only: true } })
      .then((r) => setReasons(r.data))
      .catch((e) => toast.error(getErrorMessage(e, 'No se pudieron cargar los motivos de ajuste')));
  }, [open, initialProduct]);

  const kindReasons = reasons.filter((r) => (r.applies_to || []).includes(kind));
  useEffect(() => {
    if (!kindReasons.some((r) => r.name === reason)) setReason(kindReasons[0]?.name || '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, reasons]);
  const reasonDoc = reasons.find((r) => r.name === reason);

  const addProduct = (p) => {
    if (items.some((i) => i.barcode === p.barcode)) {
      toast.error(`${p.name} ya está en el ajuste.`);
      return;
    }
    setItems([...items, { barcode: p.barcode, name: p.name, stock: p.stock, cost: p.purchase_price || 0, value: '' }]);
    setSearch('');
  };
  const setValue = (barcode, value) => setItems(items.map((i) => (i.barcode === barcode ? { ...i, value } : i)));
  const removeItem = (barcode) => setItems(items.filter((i) => i.barcode !== barcode));

  const deltaOf = (i) => {
    if (i.value === '' || Number.isNaN(Number(i.value))) return null;
    const n = Number(i.value);
    if (kind === 'entrada') return n;
    if (kind === 'salida') return -n;
    return n - i.stock;
  };
  const totalValue = items.reduce((s, i) => s + (deltaOf(i) || 0) * i.cost, 0);

  const problem = () => {
    if (!reason) return 'Elige un motivo (si no hay ninguno para este tipo, créalo en Motivos de ajuste).';
    if (reasonDoc?.requires_note && !notes.trim()) return `El motivo "${reason}" exige una observación: explica qué pasó.`;
    if (items.length === 0) return 'Agrega al menos un producto.';
    for (const i of items) {
      const n = Number(i.value);
      if (i.value === '' || !Number.isInteger(n)) return `Escribe una cantidad entera para ${i.name}.`;
      if (kind !== 'conteo' && n <= 0) return `La cantidad de ${i.name} debe ser mayor a 0.`;
      if (kind === 'conteo' && n < 0) return `Lo contado de ${i.name} no puede ser negativo.`;
      if (kind === 'salida' && n > i.stock) return `Stock insuficiente de ${i.name}: hay ${i.stock} y quieres sacar ${n}.`;
    }
    return null;
  };

  const save = async () => {
    const p = problem();
    if (p) { toast.error(p); return; }
    setSaving(true);
    try {
      const body = {
        kind, reason, notes: notes.trim() || null,
        items: items.map((i) => (kind === 'conteo'
          ? { barcode: i.barcode, counted: Number(i.value), expected_stock: i.stock }
          : { barcode: i.barcode, quantity: Number(i.value) })),
      };
      const r = await api.post(`/inventory/adjustments`, body);
      toast.success(`Ajuste ${r.data.adjustment_number} guardado · valor ${signedMoney(r.data.total_value)}`);
      onOpenChange(false);
      notifyDataChanged();
      onSaved && onSaved(r.data);
    } catch (e) {
      toast.error(getErrorMessage(e, 'No se pudo guardar el ajuste'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="adjustment-dialog">
        <DialogHeader>
          <DialogTitle>Nuevo ajuste de inventario</DialogTitle>
          <DialogDescription>Un ajuste no se puede editar ni borrar: si te equivocas, haz otro ajuste al revés.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Tipo *</Label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(KIND_LABELS).map(([k, label]) => (
                  <Button key={k} type="button" size="sm" variant={kind === k ? 'default' : 'outline'}
                          onClick={() => { setKind(k); setItems(items.map((i) => ({ ...i, value: '' }))); }}
                          data-testid={`adjustment-kind-${k}`}>
                    {label}
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{KIND_HELP[kind]}</p>
            </div>
            <div className="space-y-2">
              <Label>Motivo *</Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger data-testid="adjustment-reason-select"><SelectValue placeholder="Sin motivos para este tipo" /></SelectTrigger>
                <SelectContent>
                  {kindReasons.map((r) => <SelectItem key={r.name} value={r.name}>{r.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {reasonDoc?.description && <p className="text-xs text-muted-foreground">{reasonDoc.description}</p>}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="adj-notes">Observación{reasonDoc?.requires_note ? ' *' : ''}</Label>
            <Textarea id="adj-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
                      placeholder="Qué pasó (p. ej. se dañaron en la nevera)" data-testid="adjustment-notes" />
          </div>

          <div className="space-y-2">
            <Label>Productos *</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-10" placeholder="Buscar producto por nombre o código (mín. 2 letras)..." value={search}
                     onChange={(e) => setSearch(e.target.value)} data-testid="adjustment-product-search" />
            </div>
            {results.length > 0 && (
              <div className="border rounded-md max-h-48 overflow-y-auto divide-y">
                {results.map((p) => (
                  <button key={p.barcode} type="button" onClick={() => addProduct(p)}
                          className="w-full text-left px-3 py-2 hover:bg-muted flex justify-between text-sm">
                    <span>{p.name} <span className="font-mono text-muted-foreground">{p.barcode}</span></span>
                    <span className="text-muted-foreground">stock {p.stock}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {items.length > 0 && (
            <div className="border rounded-md overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Producto</TableHead>
                    <TableHead className="text-right">Stock</TableHead>
                    <TableHead className="text-right">{kind === 'conteo' ? 'Contado' : kind === 'entrada' ? 'Sumar' : 'Sacar'}</TableHead>
                    <TableHead className="text-right">Diferencia</TableHead>
                    <TableHead className="text-right">Queda</TableHead>
                    <TableHead className="text-right">Valor</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((i) => {
                    const d = deltaOf(i);
                    const bad = kind === 'salida' && d !== null && i.stock + d < 0;
                    return (
                      <TableRow key={i.barcode}>
                        <TableCell>{i.name}<div className="text-xs font-mono text-muted-foreground">{i.barcode}</div></TableCell>
                        <TableCell className="text-right font-mono">{i.stock}</TableCell>
                        <TableCell className="text-right">
                          <Input type="number" min="0" step="1" value={i.value} onChange={(e) => setValue(i.barcode, e.target.value)}
                                 className="w-24 ml-auto text-right" data-testid={`adjustment-qty-${i.barcode}`} />
                        </TableCell>
                        <TableCell className={`text-right font-mono ${d > 0 ? 'text-chart-1' : d < 0 ? 'text-chart-4' : ''}`}>
                          {d === null ? '—' : `${d > 0 ? '+' : ''}${d}`}
                        </TableCell>
                        <TableCell className={`text-right font-mono ${bad ? 'text-red-400' : ''}`}>{d === null ? '—' : i.stock + d}</TableCell>
                        <TableCell className="text-right font-mono">{d === null ? '—' : signedMoney(d * i.cost)}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" onClick={() => removeItem(i.barcode)} aria-label="Quitar">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Valor al costo (cantidad × precio de compra)</span>
            <span className={`font-mono font-bold text-lg ${totalValue < 0 ? 'text-red-400' : totalValue > 0 ? 'text-green-400' : ''}`}>
              {signedMoney(totalValue)}
            </span>
          </div>
          {problem() && items.length > 0 && <p className="text-sm text-amber-400" data-testid="adjustment-problem">{problem()}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={save} disabled={saving} data-testid="save-adjustment-button">
            {saving ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Guardando...</> : 'Guardar ajuste'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ------------------------------------------------------------------ pestaña «Ajustes»

export const AdjustmentsTab = ({ canAdjust, onNew, refreshKey }) => {
  const [kind, setKind] = useState('');
  const [reason, setReason] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reasons, setReasons] = useState([]);
  const [detail, setDetail] = useState(null);
  const params = { tz_offset_minutes: tz() };
  if (kind) params.kind = kind;
  if (reason) params.reason = reason;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const list = usePaginatedList(`${API}/inventory/adjustments`, { params, errorMessage: 'Error al cargar los ajustes' });
  const s = list.summary || {};

  useEffect(() => {
    api.get(`/adjustment-reasons`).then((r) => setReasons(r.data)).catch(() => setReasons([]));
  }, []);
  useEffect(() => {
    if (refreshKey) list.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const openDetail = async (number) => {
    try {
      const r = await api.get(`/inventory/adjustments/${number}`);
      setDetail(r.data);
    } catch (e) {
      toast.error(getErrorMessage(e, 'No se pudo cargar el ajuste'));
    }
  };

  return (
    <div className="space-y-4" data-testid="adjustments-tab">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input className="pl-10" placeholder="Buscar ajuste, producto, nota..." value={list.search}
                 onChange={(e) => list.setSearch(e.target.value)} data-testid="search-adjustments-input" />
        </div>
        <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}
                aria-label="Tipo" data-testid="adjustments-kind-filter">
          <option value="">Todos los tipos</option>
          {Object.entries(KIND_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={reason} onChange={(e) => setReason(e.target.value)}
                aria-label="Motivo" data-testid="adjustments-reason-filter">
          <option value="">Todos los motivos</option>
          {reasons.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
        </select>
        <Input type="date" className="w-40" value={startDate} onChange={(e) => setStartDate(e.target.value)} aria-label="Desde" />
        <Input type="date" className="w-40" value={endDate} onChange={(e) => setEndDate(e.target.value)} aria-label="Hasta" />
        <div className="ml-auto flex gap-2">
          <ExportMenu url={`${API}/inventory/adjustments/export`} fallbackName="ajustes" testId="export-adjustments-button"
                      params={{ ...params, ...(list.search.trim() ? { search: list.search.trim() } : {}) }} />
          {canAdjust && (
            <Button size="sm" onClick={onNew} data-testid="new-adjustment-button">
              <Plus className="h-4 w-4 mr-2" /> Nuevo ajuste
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-sm" data-testid="adjustments-summary">
        <span>{s.adjustments || 0} ajuste(s)</span>
        <span className="text-red-400">Pérdidas {money(s.loss_value)} ({s.units_out || 0} und.)</span>
        <span className="text-green-400">Sobrantes {money(s.gain_value)} ({s.units_in || 0} und.)</span>
        <span className="font-semibold">Neto {signedMoney(s.net_value || 0)}</span>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ajuste</TableHead>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo · Motivo</TableHead>
              <TableHead className="text-right">Productos</TableHead>
              <TableHead className="text-right">Valor</TableHead>
              <TableHead>Usuario</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.items.map((a) => (
              <TableRow key={a.adjustment_number}>
                <TableCell className="font-mono">{a.adjustment_number}</TableCell>
                <TableCell className="text-sm text-muted-foreground whitespace-nowrap">{new Date(a.created_at).toLocaleString('es-CO')}</TableCell>
                <TableCell>
                  {a.kind_label || KIND_LABELS[a.kind]} · {a.reason}
                  {a.notes && <div className="text-xs text-muted-foreground truncate max-w-xs">{a.notes}</div>}
                </TableCell>
                <TableCell className="text-right">{a.products_count}</TableCell>
                <TableCell className={`text-right font-mono ${a.total_value < 0 ? 'text-red-400' : a.total_value > 0 ? 'text-green-400' : ''}`}>
                  {signedMoney(a.total_value)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{a.created_by_name || a.created_by}</TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => openDetail(a.adjustment_number)} data-testid={`view-adjustment-${a.adjustment_number}`}>
                    <Eye className="h-4 w-4 mr-1" /> Ver
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {list.items.length === 0 && !list.loading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  No hay ajustes {kind || reason || startDate || endDate || list.search ? 'con ese filtro' : 'registrados'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <Pagination {...list.paginationProps} noun="ajuste(s)" testId="adjustments-pagination" />

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="adjustment-detail">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle>Ajuste {detail.adjustment_number}</DialogTitle>
                <DialogDescription>
                  {detail.kind_label || KIND_LABELS[detail.kind]} · {detail.reason} · {new Date(detail.created_at).toLocaleString('es-CO')} · {detail.created_by_name || detail.created_by}
                </DialogDescription>
              </DialogHeader>
              {detail.notes && <p className="text-sm p-3 rounded-md bg-muted/40">{detail.notes}</p>}
              <div className="border rounded-md overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Producto</TableHead>
                      <TableHead className="text-right">Antes</TableHead>
                      {detail.kind === 'conteo' && <TableHead className="text-right">Contado</TableHead>}
                      <TableHead className="text-right">Diferencia</TableHead>
                      <TableHead className="text-right">Después</TableHead>
                      <TableHead className="text-right">Costo</TableHead>
                      <TableHead className="text-right">Valor</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.items.map((i) => (
                      <TableRow key={i.barcode}>
                        <TableCell>{i.product_name}<div className="text-xs font-mono text-muted-foreground">{i.barcode}</div></TableCell>
                        <TableCell className="text-right font-mono">{i.stock_before}</TableCell>
                        {detail.kind === 'conteo' && <TableCell className="text-right font-mono">{i.counted}</TableCell>}
                        <TableCell className={`text-right font-mono ${i.quantity > 0 ? 'text-chart-1' : i.quantity < 0 ? 'text-chart-4' : ''}`}>
                          {i.quantity > 0 ? '+' : ''}{i.quantity}
                        </TableCell>
                        <TableCell className="text-right font-mono">{i.stock_after}</TableCell>
                        <TableCell className="text-right font-mono">{money(i.unit_cost)}</TableCell>
                        <TableCell className="text-right font-mono">{signedMoney(i.value)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex justify-end gap-4 text-sm">
                <span className="text-red-400">Pérdida {money(detail.loss_value)}</span>
                <span className="text-green-400">Sobrante {money(detail.gain_value)}</span>
                <span className="font-semibold">Neto {signedMoney(detail.total_value)}</span>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
