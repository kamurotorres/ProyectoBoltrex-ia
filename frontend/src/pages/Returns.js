import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
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
import { Plus, Search, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { usePermissions } from '@/hooks/usePermissions';

const Returns = () => {
  const { canCreate } = usePermissions();
  const [returns, setReturns] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [searchInvoice, setSearchInvoice] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [returnItems, setReturnItems] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [returnsRes, invoicesRes] = await Promise.all([
        axios.get(`${API}/returns`),
        axios.get(`${API}/invoices`)
      ]);
      setReturns(returnsRes.data);
      setInvoices(invoicesRes.data.filter(inv => inv.status === 'completed'));
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectInvoice = (invoice) => {
    setSelectedInvoice(invoice);
    setReturnItems(invoice.items.map(item => ({
      ...item,
      return_quantity: 0
    })));
  };

  const handleQuantityChange = (index, value) => {
    const newItems = [...returnItems];
    const maxQty = newItems[index].quantity;
    const qty = Math.min(parseInt(value) || 0, maxQty);
    newItems[index].return_quantity = qty;
    setReturnItems(newItems);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const itemsToReturn = returnItems.filter(item => item.return_quantity > 0);
    if (itemsToReturn.length === 0) {
      toast.error('Selecciona al menos un producto para devolver');
      return;
    }

    try {
      await axios.post(`${API}/returns`, {
        invoice_number: selectedInvoice.invoice_number,
        items: itemsToReturn.map(item => ({
          barcode: item.barcode,
          product_name: item.product_name,
          quantity: item.return_quantity,
          unit_price: item.unit_price,
          total: item.unit_price * item.return_quantity
        }))
      });
      toast.success('Devolución registrada exitosamente');
      fetchData();
      handleCloseDialog();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al registrar devolución');
    }
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setSelectedInvoice(null);
    setReturnItems([]);
    setSearchInvoice('');
  };

  const filteredInvoices = invoices.filter(inv =>
    searchInvoice === '' ||
    inv.invoice_number.toLowerCase().includes(searchInvoice.toLowerCase()) ||
    inv.client_name.toLowerCase().includes(searchInvoice.toLowerCase())
  );

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
                              <TableHead className="text-right">Cant. a Devolver</TableHead>
                              <TableHead className="text-right">Precio Unit.</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {returnItems.map((item, index) => (
                              <TableRow key={index}>
                                <TableCell>{item.product_name}</TableCell>
                                <TableCell className="text-right font-mono">{item.quantity}</TableCell>
                                <TableCell className="text-right">
                                  <Input
                                    type="number"
                                    min="0"
                                    max={item.quantity}
                                    value={item.return_quantity}
                                    onChange={(e) => handleQuantityChange(index, e.target.value)}
                                    className="w-20 text-right font-mono"
                                    data-testid={`return-quantity-${index}`}
                                  />
                                </TableCell>
                                <TableCell className="text-right font-mono">${item.unit_price.toFixed(2)}</TableCell>
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
                          ${returnItems.reduce((sum, item) => sum + (item.unit_price * item.return_quantity), 0).toFixed(2)}
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
                  <Button type="submit" data-testid="save-return-button">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Procesar Devolución
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

      {returns.length === 0 && (
        <div className="text-center py-12 text-muted-foreground" data-testid="no-returns">
          No se encontraron devoluciones registradas
        </div>
      )}
    </div>
  );
};

export default Returns;