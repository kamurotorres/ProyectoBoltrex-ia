import React, { useState } from 'react';
import axios from 'axios';
import { Download, FileSpreadsheet, FileText, FileDown, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { getErrorMessage } from '@/lib/utils';

// P2.33: «Exportar ▾» → Excel / PDF / CSV. El archivo lo arma el servidor con TODO lo del filtro activo
// (no solo la página visible). Los mensajes de error del servidor (p. ej. «el PDF admite máximo 3.000
// filas…») se muestran tal cual.
const LABELS = { xlsx: 'Excel', pdf: 'PDF', csv: 'CSV' };
const ICONS = { xlsx: FileSpreadsheet, pdf: FileText, csv: FileDown };

// El error de una descarga llega como Blob: se lee para mostrar el motivo.
const blobError = async (error) => {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      return { response: { ...error.response, data: parsed } };
    } catch {
      return error;
    }
  }
  return error;
};

export const downloadExport = async (url, params, format, fallbackName) => {
  const res = await axios.get(url, { params: { ...params, format, tz_offset_minutes: new Date().getTimezoneOffset() }, responseType: 'blob' });
  const match = (res.headers['content-disposition'] || '').match(/filename="?([^"]+)"?/);
  const link = document.createElement('a');
  link.href = URL.createObjectURL(res.data);
  link.download = match ? match[1] : `${fallbackName}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

const ExportMenu = ({ url, params = {}, formats = ['xlsx', 'pdf', 'csv'], label = 'Exportar', fallbackName = 'reporte',
                      size = 'sm', variant = 'outline', className = '', testId = 'export-menu', hint }) => {
  const [busy, setBusy] = useState(null);

  const run = async (format) => {
    setBusy(format);
    try {
      await downloadExport(url, params, format, fallbackName);
      toast.success(`Exportado en ${LABELS[format]} (completo, con el filtro activo)`);
    } catch (error) {
      toast.error(getErrorMessage(await blobError(error), `No se pudo exportar en ${LABELS[format]}`), { duration: 8000 });
    } finally {
      setBusy(null);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size={size} variant={variant} className={className} disabled={!!busy} data-testid={testId}>
          {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
          {busy ? `Exportando ${LABELS[busy]}…` : `${label} ▾`}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {hint && <><DropdownMenuLabel className="text-xs font-normal text-muted-foreground max-w-[16rem]">{hint}</DropdownMenuLabel><DropdownMenuSeparator /></>}
        {formats.map((f) => {
          const Icon = ICONS[f];
          return (
            <DropdownMenuItem key={f} onSelect={() => run(f)} data-testid={`${testId}-${f}`}>
              <Icon className="h-4 w-4 mr-2" /> {LABELS[f]}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default ExportMenu;
