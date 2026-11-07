import { z } from 'zod';

// Reglas de validación compartidas por los formularios (mantenimiento fase 6).
// Funciones puras con zod: se prueban sin navegador (tests/frontend_forms_check.js). Los valores del
// formulario son los textos tal cual se escriben; cada pantalla los convierte al enviar (igual que antes).
// El backend vuelve a validar todo: estas reglas solo avisan antes y debajo del campo.

/** Texto obligatorio: no puede quedar vacío ni con solo espacios. */
export const requiredText = (message) => z.preprocess((v) => (v === null || v === undefined ? '' : v),
  z.string({ invalid_type_error: message }).refine((v) => v.trim().length > 0, { message }));

/** Texto opcional (vacío o null = sin dato; el servidor puede devolver null). */
export const optionalText = () => z.string().nullable().optional();

// Mismo criterio práctico que EmailStr del backend para los casos comunes: algo@dominio.ext, sin espacios.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const isEmail = (v) => EMAIL_RE.test(v.trim());

/** Correo obligatorio. */
export const requiredEmail = (emptyMessage = 'Escribe el correo.') => z.preprocess((v) => v ?? '', z.string()
  .refine((v) => v.trim().length > 0, { message: emptyMessage })
  .refine((v) => !v.trim() || isEmail(v), { message: 'El correo no es válido (ejemplo: nombre@dominio.com).' }));

/** Correo opcional: vacío se acepta; si se escribe, debe ser válido. */
export const optionalEmail = () => z.string().nullable().optional()
  .refine((v) => !v || !v.trim() || isEmail(v), { message: 'El correo no es válido (ejemplo: nombre@dominio.com).' });

const isNumberText = (v) => v.trim() !== '' && Number.isFinite(Number(v.trim()));
const inRange = (v, min, max) => (min === undefined || Number(v) >= min) && (max === undefined || Number(v) <= max);
// El campo puede traer texto (lo escrito), número o null (lo que vino del servidor): se valida como texto.
const asText = (schema) => z.preprocess((v) => (v === null || v === undefined ? '' : String(v)), schema);

/** Número obligatorio con mínimo/máximo opcionales. */
export const requiredNumber = ({ min, max, message }) => asText(z.string()
  .refine((v) => isNumberText(v) && inRange(v, min, max), { message }));

/** Número opcional (vacío = sin dato) con mínimo/máximo opcionales. */
export const optionalNumber = ({ min, max, message }) => asText(z.string()
  .refine((v) => v.trim() === '' || (isNumberText(v) && inRange(v, min, max)), { message }));

/** Entero obligatorio entre min y max. */
export const requiredInt = ({ min, max, message }) => asText(z.string()
  .refine((v) => /^-?\d+$/.test(v.trim()) && inRange(v, min, max), { message }));

/** Entero opcional (vacío = sin dato) entre min y max. */
export const optionalInt = ({ min = 0, max, message }) => asText(z.string()
  .refine((v) => v.trim() === '' || (/^-?\d+$/.test(v.trim()) && inRange(v, min, max)), { message }));

// ---------------------------------------------------------------- contraseñas
// Copia de backend/core/passwords.py (password_problem). Si cambia allá, cambia aquí (la prueba lo compara).
export const MIN_PASSWORD_LENGTH = 8;
export const INSECURE_PASSWORDS = ['admin123', 'admin', '12345678', 'password', 'contraseña', 'boltrex', 'boltrex123'];

export const passwordProblem = (password) => {
  if (password === null || password === undefined || !password.trim()) return 'La contraseña no puede estar vacía.';
  if (password.length < MIN_PASSWORD_LENGTH) return `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  if (INSECURE_PASSWORDS.includes(password.trim().toLowerCase())) {
    return 'Esa contraseña es demasiado común o es la contraseña por defecto. Elige otra.';
  }
  return null;
};

/** Contraseña con las reglas del backend. */
export const password = () => z.string().superRefine((v, ctx) => {
  const problem = passwordProblem(v);
  if (problem) ctx.addIssue({ code: z.ZodIssueCode.custom, message: problem });
});

/**
 * Esquema de campos + revisiones extra que miran varios campos a la vez (p. ej. precios vs. costo).
 * A diferencia de .superRefine de zod (que no corre si algún campo falla), aquí corren SIEMPRE las dos
 * cosas y se muestran todos los errores de una vez. check(data) → [{ path, message }].
 */
export const withChecks = (schema, check) => z.any().superRefine((data, ctx) => {
  const r = schema.safeParse(data);
  if (!r.success) r.error.issues.forEach((i) => ctx.addIssue({ code: z.ZodIssueCode.custom, path: i.path, message: i.message }));
  check(data || {}).forEach(({ path, message }) => ctx.addIssue({ code: z.ZodIssueCode.custom, path, message }));
});

/** Primer mensaje de error de un objeto de errores de react-hook-form (para el aviso general). */
export const firstErrorMessage = (errors) => {
  if (!errors || typeof errors !== 'object') return null;
  for (const [key, value] of Object.entries(errors)) {
    if (!value || typeof value !== 'object' || key === 'ref' || key === 'types') continue;   // ref = elemento del DOM
    if (typeof value.message === 'string' && value.message) return value.message;
    const nested = firstErrorMessage(value);
    if (nested) return nested;
  }
  return null;
};

/** Valida datos con un esquema fuera de un formulario: devuelve el primer mensaje o null. */
export const schemaProblem = (schema, data) => {
  const r = schema.safeParse(data);
  return r.success ? null : r.error.issues[0].message;
};
