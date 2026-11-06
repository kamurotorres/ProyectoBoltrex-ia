import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { CheckCircle2, DollarSign, FileText, User } from 'lucide-react';
import { currency as formatCurrency } from '@/lib/format';

// Extraído de Fios.js (mantenimiento fase 5) sin cambios en el JSX.
export default function SummaryCards({ totals }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Clientes con Crédito</p>
              <p className="text-2xl font-bold">{totals.clients_count}</p>
            </div>
            <User className="h-8 w-8 text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Crédito</p>
              <p className="text-2xl font-bold">{formatCurrency(totals.total_credit)}</p>
            </div>
            <FileText className="h-8 w-8 text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Abonado</p>
              <p className="text-2xl font-bold text-green-400">{formatCurrency(totals.total_paid)}</p>
            </div>
            <CheckCircle2 className="h-8 w-8 text-green-400" />
          </div>
        </CardContent>
      </Card>
      <Card className="border-red-500/30">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Saldo Pendiente</p>
              <p className="text-2xl font-bold text-red-400">{formatCurrency(totals.balance)}</p>
            </div>
            <DollarSign className="h-8 w-8 text-red-400" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
