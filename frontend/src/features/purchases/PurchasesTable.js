import React from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle, Edit, Eye, Loader2 } from 'lucide-react';
import { dateTime, money } from '@/lib/format';

// Extraído de Purchases.js (mantenimiento fase 5) sin cambios en el JSX.
export default function PurchasesTable({ canUpdate, confirmingId, handleConfirm, openEditDialog, openViewDialog, purchases }) {
  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Código</TableHead>
            <TableHead>Proveedor</TableHead>
            <TableHead className="text-right font-mono">Total</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>Registrado por</TableHead>
            <TableHead>Fecha</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {purchases.map((purchase, index) => (
            <TableRow key={purchase.purchase_number || index} data-testid={`purchase-row-${index}`}>
              <TableCell className="font-mono font-semibold">{purchase.purchase_number}</TableCell>
              <TableCell>{purchase.supplier_name}</TableCell>
              <TableCell className="text-right font-mono font-bold">
                {money(purchase.total)}
              </TableCell>
              <TableCell>
                <Badge variant={purchase.status === 'confirmado' ? 'default' : 'secondary'}
                  className={purchase.status === 'confirmado' ? 'bg-green-600 hover:bg-green-700' : 'bg-yellow-600 hover:bg-yellow-700'}>
                  {purchase.status === 'confirmado' ? 'Confirmado' : 'Borrador'}
                </Badge>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">{purchase.created_by}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {dateTime(purchase.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  {purchase.status === 'borrador' ? (
                    <>
                      {canUpdate('purchases') && (
                        <Button variant="ghost" size="icon" onClick={() => openEditDialog(purchase)} title="Editar" data-testid={`edit-purchase-${index}`}>
                          <Edit className="h-4 w-4" />
                        </Button>
                      )}
                      {canUpdate('purchases') && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-green-500 hover:text-green-600"
                          onClick={() => handleConfirm(purchase.purchase_number)}
                          disabled={confirmingId === purchase.purchase_number}
                          title="Procesar"
                          data-testid={`confirm-purchase-${index}`}
                        >
                          {confirmingId === purchase.purchase_number ? (
                            <Loader2 className="h-4 w-4 animate-spin text-green-500" />
                          ) : (
                            <CheckCircle className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </>
                  ) : (
                    <Button variant="ghost" size="icon" onClick={() => openViewDialog(purchase)} title="Ver Detalle" data-testid={`view-purchase-${index}`}>
                      <Eye className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
