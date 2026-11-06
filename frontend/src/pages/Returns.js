import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Search, RotateCcw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';
import { notifyDataChanged } from '@/lib/events';
import { usePermissions } from '@/hooks/usePermissions';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';
import { API, api } from '@/api/client';

const Returns = () => {
  const { canCreate } = usePermissions();
  // P1.18: devoluciones paginadas; la factura a devolver se busca en el servidor (cualquier antigüedad).
  const list = usePaginatedList(`${API}/returns`, { errorMessage: 'Error al cargar devoluciones' });
  const returns = list.items;
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [searchInvoice, setSearchInvoice] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [returnItems, setReturnItems] = useState([]);

  // Facturas que aún admiten devolución (una con devolución parcial puede recibir más).
  // Sin texto: las 10 más recientes; con texto: búsqueda por número, cliente o documento.
  useEffect(() => {
    if (!dialogOpen) return undefined;
    const t = setTimeout(async () => {
      try {
        const params = { exclude_status: 'returned', page_size: 10 };
        if (searchInvoice.trim()) params.search = searchInvoice.trim();
        const res = await api.get(`/invoices`, { params });
        setInvoices(res.data.items || []);
      } catch (error) {
        toast.error(getErrorMessage(error, 'Error al buscar facturas'));
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchInvoice, dialogOpen]);

  useEffect(() => {
    if (!list.loading) setLoading(false);
  }, [list.loading]);

  const fetchData = async () => {
    await list.reload();
  };

  const handleSelectInvoice = async (invoice) => {
    // Unidades ya devueltas de esta factura, por producto (el backend valida lo mismo).
    // Se consultan en el servidor: la lista de abajo está paginada (P1.18).
    let previous = [];
    try {
      const res = await api.get(`/returns`, { params: { invoice_number: invoice.invoice_number, page_size: 200 } });
      previous = res.data.items || [];
    } catch (error) {
      toast.error(getErrorMessage(error, 'No se pudieron consultar las devoluciones previas de la factura'));
      return;
    }
    const returnedByBarcode = {};
    previous
      .forEach(ret => ret.items.forEach(item => {
        returnedByBarcode[item.barcode] = (returnedByBarcode[item.barcode] || 0) + item.quantity;
      }));

    setSelectedInvoice(invoice);
    setReturnItems(invoice.items.map(item => {
      // Si una referencia aparece en varias líneas, lo devuelto se descuenta línea por línea.
      const alreadyReturned = Math.min(returnedByBarcode[item.barcode] || 0, item.quantity);
      returnedByBarcode[item.barcode] = (returnedByBarcode[item.barcode] || 0) - alreadyReturned;
      return {
        ...item,
        available_quantity: item.quantity - alreadyReturned,
        return_quantity: 0
      };
    }));
  };

  const handleQuantityChange = (index, value) => {
    const newItems = [...returnItems];
    const maxQty = newItems[index].available_quantity;
    const qty = Math.max(0, Math.min(parseInt(value) || 0, maxQty));
    newItems[index].return_quantity = qty;
    setReturnItems(newItems);
  };

  // Precio unitario con IVA: es lo que se cobró y lo que se reembolsa.
  const unitPriceWithTax = (item) => item.unit_price * (1 + (item.tax_rate || 0) / 100);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    const itemsToReturn = returnItems.filter(item => item.return_quantity > 0);
    if (itemsToReturn.length === 0) {
      toast.error('Selecciona al menos un producto para devolver');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await api.post(`/returns`, {
        invoice_number: selectedInvoice.invoice_number,
        // Precio e importes los calcula el servidor a partir de la factura.
        items: itemsToReturn.map(item => ({
          barcode: item.barcode,
          product_name: item.product_name,
          quantity: item.return_quantity
        }))
      });
      notifyDataChanged();
      // P2.31: si el cliente ya había pagado más que el nuevo total, se le entrega efectivo de la caja.
      const refund = res.data?.refund_amount || 0;
      if (refund > 0) {
        toast.success(`Devolución registrada. Entrega al cliente $${Math.round(refund).toLocaleString('es-CO')} en efectivo (sale de tu caja).`, { duration: 8000 });
      } else {
        toast.success('Devolución registrada. No hay dinero que entregar: se descontó de lo que el cliente debe o de su factura.');
      }
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al registrar devolución'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setSelectedInvoice(null);
    setReturnItems([]);
    setSearchInvoice('');
  };

  const filteredInvoices = invoices;

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="returns-page">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Devoluciones</h1>
          <p className="text-muted-foreground mt-2">Gestión de devoluciones de ventas</p>
        </div>
        {canCreate('returns') && (
          <Button onClick={() => setDialogOpen(true)} data-testid="create-return-button">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Devolución
          </Button>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="return-dialog">
            <DialogHeader>
              <DialogTitle>Nueva Devolución</DialogTitle>
              <DialogDescription>Procesa la devolución de una venta</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                {!selectedInvoice ? (
                  <>
                    <div className="space-y-2">
                      <Label>Buscar Factura</Label>
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          type="text"
                          placeholder="Buscar por número de factura o cliente..."
                          value={searchInvoice}
                          onChange={(e) => setSearchInvoice(e.target.value)}
                          className="pl-10"
                          data-testid="search-invoice-input"
                        />
                      </div>
                    </div>

                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {filteredInvoices.slice(0, 10).map((invoice, index) => (
                        <Card
                          key={invoice.invoice_number}
                          className="cursor-pointer card-hover"
                          onClick={() => handleSelectInvoice(invoice)}
                          data-testid={`invoice-card-${index}`}
                        >
                          <CardContent className="p-4">
                            <div className="flex justify-between items-start">
                              <div>
                                <p className="font-mono font-semibold">{invoice.invoice_number}</p>
                                <p className="text-sm text-muted-foreground">{invoice.client_name}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-mono font-bold">${invoice.total.toFixed(2)}</p>
                                <p className="text-xs text-muted-foreground">
                                  {new Date(invoice.created_at).toLocaleDateString('es-ES')}
                                </p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="bg-secondary p-4 rounded-md">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="font-mono font-bold">{selectedInvoice.invoice_number}</p>
                          <p className="text-sm text-muted-foreground">{selectedInvoice.client_name}</p>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedInvoice(null)}
                        >
                          Cambiar
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Items a Devolver</Label>
                      <div className="border rounded-md">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Producto</TableHead>
                              <TableHead className="text-right">Cant. Original</TableHead>
                              <TableHead className="text-right">Disponible</TableHead>
                              <TableHead className="text-right">Cant. a Devolver</TableHead>
                              <TableHead className="text-right">Precio Unit. (con IVA)</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {returnItems.map((item, index) => (
                              <TableRow key={index}>
                                <TableCell>{item.product_name}</TableCell>
                                <TableCell className="text-right font-mono">{item.quantity}</TableCell>
                                <TableCell className="text-right font-mono" data-testid={`return-available-${index}`}>{item.available_quantity}</TableCell>
                                <TableCell className="text-right">
                                  <Input
                                    type="number"
                                    min="0"
                                    max={item.available_quantity}
                                    value={item.return_quantity}
                                    onChange={(e) => handleQuantityChange(index, e.target.value)}
                                    disabled={item.available_quantity === 0}
                                    className="w-20 text-right font-mono"
                                    data-testid={`return-quantity-${index}`}
                                  />
                                </TableCell>
                                <TableCell className="text-right font-mono">${unitPriceWithTax(item).toFixed(2)}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>

                    <div className="border-t pt-4">
                      <div className="flex justify-between text-lg font-bold">
                        <span>Total a Devolver:</span>
                        <span className="font-mono" data-testid="return-total">
                          ${returnItems.reduce((sum, item) => sum + (unitPriceWithTax(item) * item.return_quantity), 0).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </>
                )}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleCloseDialog}>
                  Cancelar
                </Button>
                {selectedInvoice && (
                  <Button type="submit" disabled={isSubmitting} data-testid="save-return-button">
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Procesando...
                      </>
                    ) : (
                      <>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Procesar Devolución
                      </>
                    )}
                  </Button>
                )}
              </DialogFooter>
            </form>
          </DialogContent>
      </Dialog>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Factura</TableHead>
              <TableHead className="text-right font-mono">Total Devuelto</TableHead>
              <TableHead>Procesado por</TableHead>
              <TableHead>Fecha</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {returns.map((returnItem, index) => (
              <TableRow key={index} data-testid={`return-row-${index}`}>
                <TableCell className="font-mono">{returnItem.invoice_number}</TableCell>
                <TableCell className="text-right font-mono font-bold">${returnItem.total.toFixed(2)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{returnItem.created_by}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(returnItem.created_at).toLocaleString('es-ES')}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {returns.length === 0 && !list.loading && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-returns">
          No se encontraron devoluciones registradas
        </div>
      )}
      <Pagination {...list.paginationProps} noun="devolución(es)" testId="returns-pagination" />
    </div>
  );
};

export default Returns;