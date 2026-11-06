import React, { useState, useEffect } from 'react';
import { API } from '@/App';
import ExportMenu from '@/components/ExportMenu';
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
import { FileText, Filter } from 'lucide-react';
import { toast } from 'sonner';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';

const money = (v) => '$' + Number(v || 0).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const STATUS = {
  completed: { label: 'Completada', className: 'bg-green-500/15 text-green-700 dark:text-green-400' },
  partial_return: { label: 'Dev. parcial', className: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-400' },
  returned: { label: 'Devuelta', className: 'bg-red-500/15 text-red-700 dark:text-red-400' },
};

const Reports = () => {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  // P1.18: el periodo se aplica con el botón; el detalle está paginado en el servidor y los
  // totales cubren todo el periodo. tz_offset_minutes: días locales completos (P1.14).
  const [period, setPeriod] = useState({ tz_offset_minutes: new Date().getTimezoneOffset() });
  const salesList = usePaginatedList(`${API}/reports/sales`, { params: period, errorMessage: 'Error al cargar el reporte de ventas' });
  const inventoryList = usePaginatedList(`${API}/reports/inventory`, { errorMessage: 'Error al cargar el reporte de inventario' });
  const salesReport = salesList.summary ? { summary: salesList.summary, invoices: salesList.items } : null;
  const inventoryReport = inventoryList.summary ? { summary: inventoryList.summary, products: inventoryList.items } : null;
  const loading = salesList.loading;

  const fetchReports = () => {
    if (startDate && endDate && startDate > endDate) {
      toast.error("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.");
      return;
    }
    const params = { tz_offset_minutes: new Date().getTimezoneOffset() };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    if (JSON.stringify(params) === JSON.stringify(period)) {
      salesList.reload();
      inventoryList.reload();
    } else {
      setPeriod(params);
    }
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
              {/* P1.14: bruto − devoluciones = neto. Las devoluciones se descuentan en el periodo de la venta. */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card data-testid="gross-sales-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Ventas brutas</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold font-mono">{money(salesReport.summary.gross_sales)}</div>
                    <p className="text-xs text-muted-foreground mt-1" data-testid="total-invoices-card">
                      {salesReport.summary.total_invoices} factura(s)
                      {salesReport.summary.returned_invoices > 0 && ' + ' + salesReport.summary.returned_invoices + ' devuelta(s) por completo'}
                    </p>
                  </CardContent>
                </Card>

                <Card data-testid="returns-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Devoluciones</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold font-mono text-red-600 dark:text-red-400">
                      {salesReport.summary.returns_total > 0 ? '−' : ''}{money(salesReport.summary.returns_total)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{salesReport.summary.returns_count} devolución(es)</p>
                  </CardContent>
                </Card>

                <Card data-testid="total-sales-amount-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Ventas netas</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold font-mono">{money(salesReport.summary.total_sales)}</div>
                  </CardContent>
                </Card>

                <Card data-testid="total-tax-collected-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">IVA neto</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold font-mono">{money(salesReport.summary.total_tax)}</div>
                  </CardContent>
                </Card>
              </div>


              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">Detalle de Ventas</CardTitle>
                  {/* P2.33: Excel (Facturas + Detalle + Resumen) · PDF · CSV, de TODO el periodo */}
                  <ExportMenu url={`${API}/reports/sales/export`} params={period} fallbackName="ventas" testId="export-sales-button"
                              hint="Todas las facturas del periodo, no solo la página visible." />
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
                          <TableHead className="text-right font-mono">Total neto</TableHead>
                          <TableHead>Estado</TableHead>
                          <TableHead>Fecha</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {salesReport.invoices.map((invoice, index) => (
                          <TableRow key={invoice.invoice_number} data-testid={`sales-row-${index}`}>
                            <TableCell className="font-mono">{invoice.invoice_number}</TableCell>
                            <TableCell>{invoice.client_name}</TableCell>
                            <TableCell className="text-right font-mono">{money(invoice.subtotal)}</TableCell>
                            <TableCell className="text-right font-mono">{money(invoice.total_tax)}</TableCell>
                            <TableCell className="text-right font-mono font-bold">{money(invoice.total)}</TableCell>
                            <TableCell>
                              <span className={'px-2 py-0.5 rounded-full text-xs font-medium ' + ((STATUS[invoice.status] || {}).className || 'bg-muted')}>
                                {(STATUS[invoice.status] || {}).label || invoice.status}
                              </span>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(invoice.created_at).toLocaleString('es-ES')}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  <Pagination {...salesList.paginationProps} noun="factura(s)" testId="sales-pagination" />
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
                  <ExportMenu url={`${API}/reports/inventory/export`} fallbackName="inventario" testId="export-inventory-button"
                              hint="Inventario valorizado de todos los productos." />
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
                  <Pagination {...inventoryList.paginationProps} noun="producto(s)" testId="inventory-report-pagination" />
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