import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import { addProduct, cartTotals, changeQuantity, removeLine, repriceForClient, setLineQuantity } from '@/features/pos/cart';

// Hooks del POS (mantenimiento fase 5). Lógica movida tal cual desde pages/POS.js.

// P2.30: fechas locales AAAA-MM-DD para el vencimiento de las ventas a crédito.
export const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const addDays = (days) => { const d = new Date(); d.setDate(d.getDate() + Number(days || 0)); return ymd(d); };

/** Carrito: líneas, productos vistos (para recalcular precios y stock) y operaciones con sus mensajes. */
export function useCart() {
  const [cart, setCart] = useState([]);
  // P1.18: los productos se buscan en el servidor; aquí se guardan los vistos (resultados y carrito).
  const [products, setProducts] = useState([]);

  const rememberProducts = useCallback((found) => {
    setProducts((prev) => {
      const map = new Map(prev.map((p) => [p.barcode, p]));
      found.forEach((p) => map.set(p.barcode, p));
      return Array.from(map.values());
    });
  }, []);

  // Cada operación muestra su mensaje si no se pudo (mismos textos que antes) y devuelve true si cambió.
  const apply = ({ cart: next, error }) => {
    if (error) { toast.error(error); return false; }
    setCart(next);
    return true;
  };
  const addToCart = (product, client) => apply(addProduct(cart, product, client));
  const updateQuantity = (barcode, delta) => apply(changeQuantity(cart, barcode, delta, products.find((p) => p.barcode === barcode)));
  const setQuantity = (barcode, value) => apply(setLineQuantity(cart, barcode, value, products.find((p) => p.barcode === barcode)));
  const removeFromCart = (barcode) => setCart(removeLine(cart, barcode));
  const repriceFor = (client) => setCart(repriceForClient(cart, products, client));
  const clearCart = () => setCart([]);

  // setCart: lo usa el campo de cantidad para dejarlo vacío mientras se escribe (al salir vuelve a 1).
  return { cart, setCart, products, rememberProducts, addToCart, updateQuantity, setQuantity, removeFromCart, repriceFor, clearCart,
           totals: cartTotals(cart) };
}

/** P2.30: saldo, vencido y cupo del cliente seleccionado + fecha de vencimiento sugerida para la venta a crédito. */
export function useCreditStatus(selectedClient) {
  const [creditStatus, setCreditStatus] = useState(null);
  const [dueDate, setDueDate] = useState('');
  useEffect(() => {
    setCreditStatus(null);
    if (!selectedClient) return undefined;
    let cancelled = false;
    api.get(`/credit/client-status`, {
      params: { document_number: selectedClient.document_number, document_type: selectedClient.document_type },
    }).then((r) => {
      if (cancelled) return;
      setCreditStatus(r.data);
      setDueDate(addDays(r.data.term_days));
    }).catch(() => { if (!cancelled) setCreditStatus(null); });
    return () => { cancelled = true; };
  }, [selectedClient]);
  return { creditStatus, dueDate, setDueDate };
}

/** P2.31: si la configuración exige caja abierta, el POS avisa y bloquea el cobro sin ella (el backend lo exige igual). */
export function useCashState() {
  const [cashState, setCashState] = useState({ required: false, open: true });
  const fetchCashState = useCallback(async () => {
    try {
      const [settingsRes, currentRes] = await Promise.all([
        api.get(`/cash/settings`),
        api.get(`/cash/current`).catch(() => ({ data: { session: null } })),
      ]);
      setCashState({ required: !!settingsRes.data.require_open_session, open: !!currentRes.data.session });
    } catch {
      setCashState({ required: false, open: true });
    }
  }, []);
  return { cashState, fetchCashState };
}
