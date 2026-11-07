import { toast } from 'sonner';
import { money } from '@/lib/format';

// Avisos después de procesar (confirmar) una compra — rama compras-estilo-pos, decisión 2.A:
// el backend actualiza el costo de los productos y devuelve qué cambió y qué precios quedaron bajo el costo.
export const CONFIRM_QUESTION = '¿Procesar esta compra?\nSuma las unidades al inventario, actualiza el costo de los productos '
  + 'con el de esta compra (las líneas en $0 no lo cambian) y ya no se podrá editar.';

export function notifyConfirmResult(data, purchaseNumber) {
  toast.success(`Compra ${purchaseNumber} procesada: inventario actualizado`);
  const changes = data?.cost_changes || [];
  if (changes.length) {
    const text = changes.slice(0, 4).map((c) => `${c.name} ${money(c.old_cost)} → ${money(c.new_cost)}`).join(' · ');
    toast.info(`Costo actualizado: ${text}${changes.length > 4 ? ` y ${changes.length - 4} más` : ''}`, { duration: 8000 });
  }
  const warnings = data?.price_warnings || [];
  if (warnings.length) {
    const text = warnings.slice(0, 3).map((w) => `${w.name} (costo ${money(w.new_cost)}; `
      + `${w.prices.map((p) => `${p.price_list_name} ${money(p.price)}`).join(', ')})`).join(' · ');
    toast.warning(`Precio de venta por debajo del costo nuevo: ${text}${warnings.length > 3 ? ` y ${warnings.length - 3} más` : ''}. `
      + 'Ajústalo en Productos.', { duration: 12000 });
  }
}
