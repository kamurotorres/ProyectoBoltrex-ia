import { z } from 'zod';
import { pricingIssues } from '@/features/products/pricing';
import { optionalEmail, optionalInt, optionalNumber, optionalText, password, passwordProblem, requiredEmail, requiredInt, requiredNumber, requiredText, withChecks } from './validation';

// Esquemas de los formularios (mantenimiento fase 6). Los mensajes son los mismos del backend cuando
// existe uno equivalente. Probados en tests/frontend_forms_check.js.

// ---------------------------------------------------------------- catálogos
export const categorySchema = z.object({
  name: requiredText('El nombre de la categoría no puede estar vacío'),
  description: optionalText(),
});

export const priceListSchema = z.object({
  name: requiredText('El nombre de la lista de precios no puede estar vacío'),
  description: optionalText(),
  is_active: z.boolean(),
});

export const paymentMethodSchema = z.object({
  name: requiredText('El nombre es requerido'),
  description: optionalText(),
  is_active: z.boolean(),
});

export const adjustmentReasonSchema = z.object({
  name: requiredText('Escribe el nombre del motivo.'),
  description: optionalText(),
  applies_to: z.array(z.enum(['entrada', 'salida', 'conteo']))
    .min(1, 'Marca al menos un tipo de ajuste (entrada, salida o conteo) para el motivo.'),
  requires_note: z.boolean(),
  is_active: z.boolean(),
});

// ---------------------------------------------------------------- productos
// Precio de compra, IVA y precios por lista: reglas de features/products/pricing.js (= backend core/pricing.py).
export const productSchema = withChecks(z.object({
  barcode: requiredText('Escribe el código de barras.'),
  name: requiredText('Escribe el nombre del producto.'),
  description: optionalText(),
  category: requiredText('Selecciona la categoría.'),
  min_stock: optionalInt({ min: 0, max: 1000000, message: 'El stock mínimo debe ser un número entero entre 0 y 1.000.000.' }),
}), pricingIssues);

// ---------------------------------------------------------------- terceros
export const supplierSchema = z.object({
  name: requiredText('El nombre del proveedor no puede estar vacío'),
  contact_name: optionalText(),
  phone: optionalText(),
  email: optionalEmail(),
  address: optionalText(),
});

// P2.30: plazo 0–3650 días (backend core/credit.py MAX_TERM_DAYS) y cupo ≥ 0; vacío = por defecto / sin límite.
export const clientSchema = z.object({
  document_type: requiredText('Selecciona el tipo de documento.'),
  document_number: requiredText('Escribe el número de documento.'),
  first_name: requiredText('Escribe los nombres.'),
  last_name: requiredText('Escribe los apellidos.'),
  phone: optionalText(),
  email: optionalEmail(),
  address: optionalText(),
  latitude: optionalNumber({ min: -90, max: 90, message: 'La latitud debe ser un número entre -90 y 90.' }),
  longitude: optionalNumber({ min: -180, max: 180, message: 'La longitud debe ser un número entre -180 y 180.' }),
  price_list: requiredText('Elige la lista de precios.'),
  credit_days: optionalInt({ min: 0, max: 3650, message: 'El plazo debe ser un número entero de días entre 0 y 3650.' }),
  credit_limit: optionalNumber({ min: 0, message: 'El cupo debe ser un valor de 0 o más.' }),
});

// ---------------------------------------------------------------- compras
// Proveedor elegido de la lista + al menos una fila; cada fila con cantidad entera ≥ 1 y costo ≥ 0.
export const purchaseSchema = z.object({
  supplier: z.object({ name: z.string() }).passthrough().nullable()
    .refine((v) => !!(v && v.name), { message: 'Selecciona un proveedor' }),
  items: z.array(z.object({
    quantity: requiredInt({ min: 1, message: 'La cantidad debe ser un número entero mayor a 0.' }),
    unit_cost: requiredNumber({ min: 0, message: 'El costo unitario debe ser un número de 0 o más.' }),
  }).passthrough()).min(1, { message: 'Agrega al menos un producto' }),
});

// ---------------------------------------------------------------- usuarios
// Al crear la contraseña es obligatoria; al editar, vacía = no cambiarla (el backend la ignora) y si se
// escribe debe cumplir las mismas reglas.
const userBase = {
  first_name: requiredText('Escribe los nombres.'),
  last_name: requiredText('Escribe los apellidos.'),
  email: requiredEmail('Escribe el correo.'),
  phone: optionalText(),
  is_active: z.boolean(),
};
export const userCreateSchema = z.object({ ...userBase, password: password() });
export const userEditSchema = z.object({
  ...userBase,
  password: z.string().refine((v) => !v.trim() || !passwordProblem(v), (v) => ({ message: passwordProblem(v) || '' })),
});

// ---------------------------------------------------------------- configuración del ticket
export const ticketConfigSchema = z.object({
  company_name: requiredText('El nombre de la empresa es requerido'),
  nit: optionalText(),
  phone: optionalText(),
  email: optionalEmail(),
  address: optionalText(),
  ticket_width: z.coerce.number().refine((v) => v === 58 || v === 80, { message: 'Elige el ancho del papel: 58 mm u 80 mm.' }),
  footer_message: optionalText(),
});
