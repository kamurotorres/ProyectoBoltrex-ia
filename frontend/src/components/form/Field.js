import React from 'react';
import { Controller } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

// Campos de formulario con su error debajo (mantenimiento fase 6). Se usan con hooks/useZodForm.

/** Mensaje de error de un campo (nada si no hay error). */
export const FieldError = ({ error, id }) => (error?.message
  ? <p className="text-sm text-destructive" role="alert" id={id} data-testid={id}>{error.message}</p>
  : null);

/** Etiqueta + control cualquiera (select, switch…) + error debajo. */
export const Field = ({ label, htmlFor, error, hint, className, children }) => (
  <div className={cn('space-y-2', className)}>
    {label && <Label htmlFor={htmlFor} className={cn(error && 'text-destructive')}>{label}</Label>}
    {children}
    {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
    <FieldError error={error} id={htmlFor ? `${htmlFor}-error` : undefined} />
  </div>
);

/** Etiqueta + Input registrado en el formulario + error debajo. `name` admite rutas ("prices.0.price"). */
// registerOptions: opciones de react-hook-form (p. ej. { deps: 'prices' } para revalidar otro campo al cambiar este).
export const TextField = ({ form, name, label, id, hint, className, registerOptions, ...inputProps }) => {
  const error = name.split('.').reduce((acc, k) => (acc ? acc[k] : undefined), form.formState.errors);
  const inputId = id || name;
  return (
    <Field label={label} htmlFor={inputId} error={error} hint={hint} className={className}>
      <Input id={inputId} aria-invalid={!!error} className={cn(error && 'border-destructive')} {...form.register(name, registerOptions)} {...inputProps} />
    </Field>
  );
};

/** Interruptor (sí/no) registrado en el formulario, con su etiqueta a la derecha. */
export const SwitchField = ({ form, name, label, id, className, ...switchProps }) => (
  <Controller
    control={form.control}
    name={name}
    render={({ field }) => (
      <div className={cn('flex items-center gap-3', className)}>
        <Switch id={id || name} checked={!!field.value} onCheckedChange={field.onChange} {...switchProps} />
        <Label htmlFor={id || name}>{label}</Label>
      </div>
    )}
  />
);

/** Lista desplegable registrada en el formulario + error debajo. options = [{ value, label }]. */
export const SelectField = ({ form, name, label, id, placeholder, options, disabled, triggerTestId, className }) => (
  <Controller
    control={form.control}
    name={name}
    render={({ field, fieldState }) => (
      <Field label={label} htmlFor={id || name} error={fieldState.error} className={className}>
        <Select value={field.value ?? ''} onValueChange={field.onChange} disabled={disabled}>
          <SelectTrigger id={id || name} aria-invalid={!!fieldState.error} data-testid={triggerTestId}
                         className={cn(fieldState.error && 'border-destructive')}>
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </Field>
    )}
  />
);

export default TextField;
