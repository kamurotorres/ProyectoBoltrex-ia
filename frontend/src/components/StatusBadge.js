import React from 'react';

// P2.30: estado de una cuenta / factura (al día · por vencer · vencida).
const STATUS_STYLE = {
  overdue: 'bg-red-500/15 text-red-400 border-red-500/30',
  due_soon: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  current: 'bg-green-500/15 text-green-400 border-green-500/30',
};
export const StatusBadge = ({ status, label }) => (
  <span className={`inline-block px-2 py-0.5 rounded-full border text-xs whitespace-nowrap ${STATUS_STYLE[status] || STATUS_STYLE.current}`}>
    {label}
  </span>
);

// Compartido (mantenimiento fase 5): Fios lo usa en cuentas y facturas.
export default StatusBadge;
