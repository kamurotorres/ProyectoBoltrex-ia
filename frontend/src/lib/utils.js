import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Mensaje legible para mostrar al usuario a partir de un error de axios.
 *
 * El backend explica en `detail` por qué no se pudo hacer una acción
 * (p. ej. "No se puede eliminar la categoría 'X': está asignada a 3 producto(s)...").
 * - `detail` texto  → se muestra tal cual.
 * - `detail` lista  → errores de validación de FastAPI (422): se unen sus mensajes.
 * - sin respuesta   → problema de red.
 */
export function getErrorMessage(error, fallback = 'Ocurrió un error inesperado') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc.filter((p) => p !== 'body').join('.') : '';
        return field ? `${field}: ${d?.msg}` : d?.msg;
      })
      .filter(Boolean)
      .join(' · ');
  }
  if (error?.request && !error?.response) return 'No se pudo conectar con el servidor';
  return fallback;
}
