import { useCallback, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { firstErrorMessage } from '@/lib/validation';

// Formulario con react-hook-form + zod (mantenimiento fase 6).
//   const form = useZodForm(schema, { name: '' });
//   <form onSubmit={form.submit(async (values) => { ... })} noValidate>
//     <TextField form={form} name="name" label="Nombre" />
// - Valida al enviar; después de un intento fallido, revalida cada campo mientras se corrige.
// - Si hay errores: cada uno sale debajo de su campo y además el primero como aviso (como antes).
// - `form.submitting` es true mientras corre onValid (para deshabilitar el botón y evitar doble envío).
// - raw: al guardar llegan los valores TAL CUAL están en el formulario (zod solo valida, no quita campos ni
//   convierte): cada pantalla arma lo que envía igual que antes.
// - El esquema puede cambiar entre renders (p. ej. crear / editar): siempre se valida con el actual.
export function useZodForm(schema, defaultValues) {
  const schemaRef = useRef(schema);
  schemaRef.current = schema;
  const resolver = useCallback((values, context, options) => zodResolver(schemaRef.current, undefined, { raw: true })(values, context, options), []);
  const form = useForm({ resolver, defaultValues, mode: 'onSubmit', reValidateMode: 'onChange' });
  const submit = (onValid) => form.handleSubmit(onValid, (errors) => {
    const message = firstErrorMessage(errors);
    if (message) toast.error(message);
  });
  return { ...form, submit, submitting: form.formState.isSubmitting, errors: form.formState.errors };
}

export default useZodForm;
