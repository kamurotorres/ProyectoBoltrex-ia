import React from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Edit, Trash2 } from 'lucide-react';
import { money } from '@/lib/format';

// Extraído de Products.js (mantenimiento fase 5) sin cambios en el JSX.
export default function ProductsTable({ canDelete, canUpdate, filteredProducts, handleDelete, handleOpenDialog }) {
  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Código</TableHead>
            <TableHead>Nombre</TableHead>
            <TableHead>Categoría</TableHead>
            <TableHead className="text-right font-mono">Stock</TableHead>
            <TableHead className="text-right font-mono">P. Compra</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredProducts.map((product, index) => (
            <TableRow key={product.barcode} data-testid={`product-row-${index}`}>
              <TableCell className="font-mono">{product.barcode}</TableCell>
              <TableCell>{product.name}</TableCell>
              <TableCell>{product.category}</TableCell>
              <TableCell className="text-right font-mono">{product.stock}</TableCell>
              <TableCell className="text-right font-mono">{money(product.purchase_price)}</TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  {canUpdate('products') && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenDialog(product)}
                      data-testid={`edit-product-${index}`}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                  {canDelete('products') && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(product.barcode)}
                      data-testid={`delete-product-${index}`}
                    >
                      <Trash2 className="h-4 w-4" />
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
