// Estado de la sesión compartido entre pestañas del mismo navegador (backlog P1.11).
// Se guarda en localStorage para que la actividad en una pestaña mantenga viva la sesión
// en todas y el aviso de inactividad no salga en una pestaña olvidada.

const ACTIVITY_KEY = 'boltrex_last_activity';        // última acción del usuario (teclado, mouse, petición)
const CONTACT_KEY = 'boltrex_last_server_contact';   // última petición al servidor
const REASON_KEY = 'boltrex_logout_reason';          // motivo del cierre, para mostrarlo en el login

export const MSG_IDLE = 'Tu sesión se cerró por inactividad. Inicia sesión de nuevo.';

const read = (key) => {
  try {
    return Number(localStorage.getItem(key)) || 0;
  } catch {
    return 0;
  }
};

const write = (key, value) => {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // Sin almacenamiento (modo privado): el servidor sigue controlando la inactividad.
  }
};

export const getLastActivity = () => read(ACTIVITY_KEY);
export const getLastServerContact = () => read(CONTACT_KEY);
export const markActivity = () => write(ACTIVITY_KEY, Date.now());

// Toda petición al servidor cuenta como actividad (así lo registra también el backend).
export const markServerContact = () => {
  const now = Date.now();
  write(CONTACT_KEY, now);
  write(ACTIVITY_KEY, now);
};

export const setLogoutReason = (reason) => {
  try {
    if (reason) sessionStorage.setItem(REASON_KEY, reason);
  } catch {
    /* sin almacenamiento */
  }
};

export const takeLogoutReason = () => {
  try {
    const reason = sessionStorage.getItem(REASON_KEY);
    sessionStorage.removeItem(REASON_KEY);
    return reason;
  } catch {
    return null;
  }
};
