import React, { useMemo, useRef, useState } from 'react';
import { money as fmtMoney } from '@/lib/format';

// Gráficas del Dashboard (backlog P2.29) en SVG propio, sin librerías.
// Reglas de la guía de visualización:
// - Una sola serie por gráfica → un solo color (--viz-series, validado contra la superficie
//   oscura de las tarjetas: contraste ≥ 3:1) y sin leyenda (el título la nombra).
// - Barras ≤ 24 px, extremo redondeado 4 px y base recta, 2 px de aire entre barras vecinas.
// - Ejes y cuadrícula discretos; los textos usan los colores de texto, nunca el de la serie.
// - Tooltip al pasar el mouse/tocar (área de toque más grande que la barra) y "Ver tabla".

export const VIZ_STYLE = { '--viz-series': '#3987e5', '--viz-series-hover': '#5a9dec' };

export const money = fmtMoney;

// Escala "bonita" para el eje Y (0, 25k, 50k…)
function niceMax(max) {
  if (!max || max <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(max)));
  const f = max / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * exp;
}

const compact = (v) => {
  const n = Number(v || 0);
  if (n >= 1e6) return `$${(n / 1e6).toLocaleString('es-CO', { maximumFractionDigits: 1 })} M`;
  if (n >= 1e3) return `$${(n / 1e3).toLocaleString('es-CO', { maximumFractionDigits: 0 })} mil`;
  return `$${n.toLocaleString('es-CO', { maximumFractionDigits: 0 })}`;
};

// Barra con extremo redondeado y base recta (vertical u horizontal).
function barPath(x, y, w, h, vertical) {
  const r = Math.min(4, vertical ? w / 2 : h / 2, vertical ? h : w);
  if (vertical) {
    if (h <= 0) return '';
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  }
  if (w <= 0) return '';
  return `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`;
}

export function ChartCard({ title, subtitle, children, table, testId }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div className="bg-card border border-border rounded-lg p-4" style={VIZ_STYLE} data-testid={testId}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="font-semibold text-sm">{title}</h3>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
        {table && (
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline shrink-0"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
          >
            {showTable ? 'Ver gráfica' : 'Ver tabla'}
          </button>
        )}
      </div>
      {showTable ? table : children}
    </div>
  );
}

export function DataTable({ columns, rows }) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>{columns.map((c) => <th key={c.key} className={`py-1.5 px-2 font-medium ${c.align === 'right' ? 'text-right' : 'text-left'}`}>{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r, i) => (
            <tr key={i}>{columns.map((c) => <td key={c.key} className={`py-1.5 px-2 ${c.align === 'right' ? 'text-right font-mono' : ''}`}>{c.format ? c.format(r[c.key], r) : r[c.key]}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Columnas verticales (ventas por día/semana/mes, ventas por hora).
export function ColumnChart({ data, valueKey = 'net', labelKey = 'label', tooltip, height = 220, labelEvery = 1, ariaLabel }) {
  const ref = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 640;
  const pad = { top: 10, right: 8, bottom: 26, left: 56 };
  const innerW = W - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d[valueKey] || 0))), [data, valueKey]);
  const slot = innerW / Math.max(1, data.length);
  const barW = Math.max(2, Math.min(24, slot - 2));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const empty = data.every((d) => !d[valueKey]);

  return (
    <div className="relative" ref={ref}>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full h-auto" role="img" aria-label={ariaLabel}>
        {ticks.map((t) => {
          const y = pad.top + innerH - (t / max) * innerH;
          return (
            <g key={t}>
              <line x1={pad.left} x2={W - pad.right} y1={y} y2={y} stroke="hsl(var(--border))" strokeWidth="1" />
              <text x={pad.left - 6} y={y + 3} textAnchor="end" fontSize="10" fill="hsl(var(--muted-foreground))">{compact(t)}</text>
            </g>
          );
        })}
        {data.map((d, i) => {
          const v = d[valueKey] || 0;
          const h = (v / max) * innerH;
          const x = pad.left + i * slot + (slot - barW) / 2;
          const y = pad.top + innerH - h;
          return (
            <g key={i}>
              <path d={barPath(x, y, barW, h, true)} fill={hover === i ? 'var(--viz-series-hover)' : 'var(--viz-series)'} />
              {/* área de toque: toda la franja */}
              <rect
                x={pad.left + i * slot} y={pad.top} width={slot} height={innerH} fill="transparent"
                onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)} onBlur={() => setHover(null)} onTouchStart={() => setHover(i)}
                tabIndex={0} aria-label={tooltip ? tooltip(d).join(', ') : `${d[labelKey]}: ${fmtMoney(v)}`}
              />
              {i % labelEvery === 0 && (
                <text x={pad.left + i * slot + slot / 2} y={height - 8} textAnchor="middle" fontSize="10" fill="hsl(var(--muted-foreground))">
                  {d[labelKey]}
                </text>
              )}
            </g>
          );
        })}
        <line x1={pad.left} x2={W - pad.right} y1={pad.top + innerH} y2={pad.top + innerH} stroke="hsl(var(--muted-foreground))" strokeOpacity="0.5" />
      </svg>
      {empty && <p className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">Sin ventas en este periodo</p>}
      {hover !== null && tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md"
          style={{ left: `${((pad.left + hover * slot + slot / 2) / W) * 100}%`, top: 0, transform: 'translateX(-50%)' }}
        >
          {tooltip(data[hover]).map((line, k) => <div key={k} className={k === 0 ? 'font-semibold' : 'text-muted-foreground'}>{line}</div>)}
        </div>
      )}
    </div>
  );
}

// Barras horizontales con el valor en la punta (formas de pago, top productos).
export function BarList({ items, value, label, detail, ariaLabel, emptyText = 'Sin datos en este periodo' }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(0, ...items.map(value));
  if (!items.length) return <p className="text-sm text-muted-foreground py-8 text-center">{emptyText}</p>;
  return (
    <ul className="space-y-2" aria-label={ariaLabel}>
      {items.map((it, i) => {
        const pct = max ? (value(it) / max) * 100 : 0;
        return (
          <li
            key={i}
            className="text-xs"
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
            title={detail ? detail(it) : undefined}
          >
            <div className="flex items-baseline justify-between gap-2 mb-1">
              <span className="truncate">{label(it)}</span>
              <span className="font-mono shrink-0">{detail ? detail(it) : value(it)}</span>
            </div>
            {/* Barra de 10 px: base recta a la izquierda, extremo redondeado 4 px en la punta */}
            <div className="h-2.5 w-full rounded-sm bg-muted" aria-hidden="true">
              <div
                className="h-full"
                style={{
                  width: `${Math.max(pct, 0.5)}%`,
                  borderRadius: '0 4px 4px 0',
                  background: hover === i ? 'var(--viz-series-hover)' : 'var(--viz-series)',
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
