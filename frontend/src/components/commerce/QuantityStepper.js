import React from 'react';
import { Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Cantidad con − / + y campo editable (sacado TAL CUAL del carrito del POS) — rama compras-estilo-pos.
//   onStep(±1) · onType(texto) mientras se escribe ('' permitido) · onBlurEmpty() si queda vacía o ≤ 0.
export default function QuantityStepper({ value, onStep, onType, onBlurEmpty, testId }) {
  return (
    <div className="flex items-center justify-center gap-2">
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8"
        onClick={() => onStep(-1)}
        type="button"
      >
        <Minus className="h-4 w-4" />
      </Button>
      <input
        type="number"
        min="1"
        className="w-16 text-center font-mono font-bold bg-transparent border rounded-md h-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        value={value}
        onFocus={(e) => e.target.select()}
        onChange={(e) => onType(e.target.value)}
        onBlur={(e) => {
          if (!e.target.value || parseInt(e.target.value) <= 0) {   // eslint-disable-line radix -- igual que el original
            onBlurEmpty();
          }
        }}
        data-testid={testId}
      />
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8"
        onClick={() => onStep(1)}
        type="button"
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
}
