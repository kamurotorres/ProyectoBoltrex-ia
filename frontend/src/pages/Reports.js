import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { FileText, Download, Filter } from 'lucide-react';
import { toast } from 'sonner';

const Reports = () => {
  const [salesReport, setSalesReport] = useState(null);
  const [inventoryReport, setInventoryReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const [salesRes, inventoryRes] = await Promise.all([
        axios.get(`${API}/reports/sales`, { params }),
        axios.get(`${API}/reports/inventory`)
      ]);
      setSalesReport(salesRes.data);
      setInventoryReport(inventoryRes.data);
    } catch (error) {
      toast.error('Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = (data, filename) => {
    if (!data || data.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map(row => headers.map(header => {
        const value = row[header];
        return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
      }).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    toast.success('Reporte exportado exitosamente');
  };

  if (loading && !salesReport) {
    return <div className="text-center py-12">Cargando reportes...</div>;
  }

  return (
    <div data-testid="reports-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Reportes</h1>
        <p className="text-muted-foreground mt-2">Análisis y estadísticas del negocio</p>
      </div>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filtros
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start-date">Fecha Inicio</Label>
              <Input
                id="start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                data-testid="start-date-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end-date">Fecha Fin</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                data-testid="end-date-input"
              />
            </div>
            <div className="flex items-end">
              <Button onClick={fetchReports} className="w-full" data-testid="apply-filters-button">
                <Filter className="h-4 w-4 mr-2" />
                Aplicar Filtros
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="sales" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sales" data-testid="tab-sales">Reporte de Ventas</TabsTrigger>
          <TabsTrigger value="inventory" data-testid="tab-inventory-report">Reporte de Inventario</TabsTrigger>
        </TabsList>

        <TabsContent value="sales" className="space-y-4">
          {salesReport && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card data-testid="total-invoices-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Facturas</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">{salesReport.summary.total_invoices}</div>
                  </CardContent>
                </Card>

                <Card data-testid="total-sales-amount-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Ventas</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">${salesReport.summary.total_sales.toFixed(2)}</div>
                  </CardContent>
                </Card>

                <Card data-testid="total-tax-collected-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">IVA Recaudado</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">${salesReport.summary.total_tax.toFixed(2)}</div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">Detalle de Ventas</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExportCSV(
                      salesReport.invoices.map(inv => ({
                        invoice_number: inv.invoice_number,
                        client_name: inv.client_name,
                        subtotal: inv.subtotal,
                        tax: inv.total_tax,
                        total: inv.total,
                        created_at: new Date(inv.created_at).toLocaleString('es-ES')
                      })),
                      'ventas'
                    )}
                    data-testid="export-sales-button"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Exportar CSV
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="border rounded-md">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Factura</TableHead>
                          <TableHead>Cliente</TableHead>
                          <TableHead className="text-right font-mono">Subtotal</TableHead>
                          <TableHead className="text-right font-mono">IVA</TableHead>
                          <TableHead className="text-right font-mono">Total</TableHead>
                          <TableHead>Fecha</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {salesReport.invoices.map((invoice, index) => (
                          <TableRow key={invoice.invoice_number} data-testid={`sales-row-${index}`}>
                            <TableCell className="font-mono">{invoice.invoice_number}</TableCell>
                            <TableCell>{invoice.client_name}</TableCell>
                            <TableCell className="text-right font-mono">${invoice.subtotal.toFixed(2)}</TableCell>
                            <TableCell className="text-right font-mono">${invoice.total_tax.toFixed(2)}</TableCell>
                            <TableCell className="text-right font-mono font-bold">${invoice.total.toFixed(2)}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(invoice.created_at).toLocaleString('es-ES')}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="inventory" className="space-y-4">
          {inventoryReport && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card data-testid="total-products-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Productos</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">{inventoryReport.summary.total_products}</div>
                  </CardContent>
                </Card>

                <Card data-testid="inventory-value-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Valor Inventario</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">${inventoryReport.summary.total_value.toFixed(2)}</div>
                  </CardContent>
                </Card>

                <Card data-testid="low-stock-report-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Productos Bajo Stock</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold font-mono">{inventoryReport.summary.low_stock_count}</div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">Detalle de Inventario</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExportCSV(
                      inventoryReport.products.map(p => ({
                        barcode: p.barcode,
                        name: p.name,
                        category: p.category,
                        stock: p.stock,
                        purchase_price: p.purchase_price,
                        total_value: p.purchase_price * p.stock
                      })),
                      'inventario'
                    )}
                    data-testid="export-inventory-button"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Exportar CSV
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="border rounded-md">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Código</TableHead>
                          <TableHead>Producto</TableHead>
                          <TableHead>Categoría</TableHead>
                          <TableHead className="text-right font-mono">Stock</TableHead>
                          <TableHead className="text-right font-mono">P. Compra</TableHead>
                          <TableHead className="text-right font-mono">Valor Total</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {inventoryReport.products.map((product, index) => (
                          <TableRow key={product.barcode} data-testid={`inventory-report-row-${index}`}>
                            <TableCell className="font-mono">{product.barcode}</TableCell>
                            <TableCell>{product.name}</TableCell>
                            <TableCell>{product.category}</TableCell>
                            <TableCell className="text-right font-mono">{product.stock}</TableCell>
                            <TableCell className="text-right font-mono">${product.purchase_price.toFixed(2)}</TableCell>
                            <TableCell className="text-right font-mono font-bold">
                              ${(product.purchase_price * product.stock).toFixed(2)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Reports;