// P2.34: aviso entre pantallas de que cambiaron datos que afectan las alertas (stock, créditos).
// Lo emiten el POS, Compras, Ajustes, Devoluciones y Fios; lo escucha la campana de alertas.
export const DATA_CHANGED = 'boltrex:data-changed';

export const notifyDataChanged = () => {
  try {
    window.dispatchEvent(new Event(DATA_CHANGED));
  } catch {
    // navegadores muy antiguos: la campana igual se refresca cada 2 minutos
  }
};
