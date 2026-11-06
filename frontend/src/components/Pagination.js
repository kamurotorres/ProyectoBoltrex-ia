import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PAGE_SIZES } from '@/hooks/usePaginatedList';

// Barra de paginación común para los listados del servidor (backlog P1.18).
const Pagination = ({ page, pages, total, pageSize, loading, onPageChange, onPageSizeChange, noun = 'registro(s)', testId = 'pagination' }) => (
  <div className="flex flex-wrap items-center justify-between gap-2 px-1 py-3 text-sm" data-testid={testId}>
    <span className="text-muted-foreground">
      {total.toLocaleString('es-CO')} {noun} · página {Math.min(page, pages)} de {pages}
    </span>
    <div className="flex items-center gap-2">
      <label className="flex items-center gap-1 text-muted-foreground">
        <span className="hidden sm:inline">Por página</span>
        <select
          className="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          data-testid={`${testId}-size`}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => onPageChange(page - 1)} data-testid={`${testId}-prev`}>
        <ChevronLeft className="h-4 w-4 mr-1" /> Anterior
      </Button>
      <Button size="sm" variant="outline" disabled={page >= pages || loading} onClick={() => onPageChange(page + 1)} data-testid={`${testId}-next`}>
        Siguiente <ChevronRight className="h-4 w-4 ml-1" />
      </Button>
    </div>
  </div>
);

export default Pagination;
