import React from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { FILTERS } from '@/features/fios/constants';
import { Button } from '@/components/ui/button';
import ExportMenu from '@/components/ExportMenu';
import { API } from '@/api/client';

// Extraído de Fios.js (mantenimiento fase 5) sin cambios en el JSX.
export default function FiltersBar({ aging, searchTerm, setSearchTerm, setStatusFilter, statusFilter }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por cliente o documento..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
          data-testid="fios-search-input"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Button key={f.key || 'all'} size="sm" variant={statusFilter === f.key ? 'default' : 'outline'}
                  onClick={() => setStatusFilter(f.key)} data-testid={`fios-filter-${f.key || 'all'}`}>
            {f.label}
          </Button>
        ))}
        {statusFilter && !FILTERS.some((f) => f.key === statusFilter) && (
          <Button size="sm" variant="default" onClick={() => setStatusFilter('')}>
            Vencido {aging?.buckets.find((b) => b.key === statusFilter)?.label || statusFilter} ✕
          </Button>
        )}
      </div>
      <ExportMenu url={`${API}/fios/export`} className="ml-auto" fallbackName="cartera" testId="fios-export-button"
                  params={{ ...(statusFilter ? { status: statusFilter } : {}), ...(searchTerm.trim() ? { search: searchTerm.trim() } : {}) }}
                  hint="Cartera completa con el filtro activo y los tramos de antigüedad." />
    </div>
  );
}
