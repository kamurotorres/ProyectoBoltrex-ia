import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { buttonVariants } from '@/components/ui/button';

// Confirmación con el estilo de la app (mantenimiento fase 4), en vez del cuadro gris de window.confirm.
//   const confirm = useConfirm();
//   if (!(await confirm('¿Eliminar este producto?', { confirmLabel: 'Eliminar', destructive: true }))) return;
// Mismo comportamiento que window.confirm: true si acepta, false si cancela o cierra (Esc / clic fuera).
const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null);   // { message, title, confirmLabel, destructive }
  const resolver = useRef(null);

  const confirm = useCallback((message, options = {}) => new Promise((resolve) => {
    resolver.current = resolve;
    setState({ message, title: options.title || '¿Confirmas?', confirmLabel: options.confirmLabel || 'Aceptar',
               destructive: !!options.destructive });
  }), []);

  const close = (value) => {
    if (resolver.current) resolver.current(value);
    resolver.current = null;
    setState(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <AlertDialog open={!!state} onOpenChange={(open) => { if (!open) close(false); }}>
        <AlertDialogContent data-testid="confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{state?.title}</AlertDialogTitle>
            <AlertDialogDescription className="whitespace-pre-line">{state?.message}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => close(false)} data-testid="confirm-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => close(true)} data-testid="confirm-accept"
                               className={state?.destructive ? buttonVariants({ variant: 'destructive' }) : undefined}>
              {state?.confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmContext.Provider>
  );
}

export const useConfirm = () => {
  const ctx = useContext(ConfirmContext);
  // Sin provider (p. ej. en una prueba aislada) se usa el cuadro nativo: nunca deja la acción sin confirmar.
  return ctx || ((message) => Promise.resolve(window.confirm(message)));
};

export default ConfirmProvider;
