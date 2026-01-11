import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  FileText, 
  Search, 
  Filter, 
  Download, 
  Eye, 
  X, 
  ChevronLeft, 
  ChevronRight,
  Calendar,
  User,
  Receipt
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { API } from '@/App';

const Invoices = () => {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, limit: 10, total: 0, pages: 1 });
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  // Filters
  const [filters, setFilters] = useState({
    start_date: '',
    end_date: '',
    client_document: '',
    user_email: '',
    invoice_number: '',
    status: ''
  });

  const fetchInvoices = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('page', pagination.page);
      params.append('limit', pagination.limit);
      
      // Add active filters
      Object.entries(filters).forEach(([key, value]) => {
        if (value && value !== 'all') {
          params.append(key, value);
        }
      });
      
      const response = await axios.get(`${API}/pos/invoices?${params.toString()}`);
      setInvoices(response.data.invoices);
      setPagination(prev => ({
        ...prev,
        total: response.data.pagination.total,
        pages: response.data.pagination.pages
      }));
    } catch (error) {
      toast.error('Error al cargar las facturas');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [pagination.page, pagination.limit, filters]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPagination(prev => ({ ...prev, page: 1 })); // Reset to first page
  };

  const clearFilters = () => {
    setFilters({
      start_date: '',
      end_date: '',
      client_document: '',
      user_email: '',
      invoice_number: '',
      status: ''
    });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const downloadTicket = async (invoiceNumber) => {
    try {
      const response = await axios.get(`${API}/pos/invoices/${invoiceNumber}/ticket`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ticket_${invoiceNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Ticket descargado');
    } catch (error) {
      toast.error('Error al descargar el ticket');
      console.error(error);
    }
  };

  const viewInvoiceDetail = (invoice) => {
    setSelectedInvoice(invoice);
    setShowDetail(true);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('es-CO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      completed: { label: 'Completada', className: 'bg-green-500/20 text-green-400' },
      returned: { label: 'Devuelta', className: 'bg-red-500/20 text-red-400' },
      partial_return: { label: 'Dev. Parcial', className: 'bg-yellow-500/20 text-yellow-400' }
    };
    const config = statusConfig[status] || { label: status, className: 'bg-gray-500/20 text-gray-400' };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        {config.label}
      </span>
    );
  };

  return (
    <div className="space-y-6" data-testid="invoices-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" data-testid="invoices-title">
            <Receipt className="h-6 w-6" />
            Facturas POS
          </h1>
          <p className="text-muted-foreground mt-1">Gestión y consulta de facturas de venta</p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => setShowFilters(!showFilters)}
          data-testid="toggle-filters-btn"
        >
          <Filter className="h-4 w-4 mr-2" />
          Filtros
        </Button>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-card border border-border rounded-lg p-4 space-y-4" data-testid="filters-panel">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="space-y-2">
              <Label>Fecha Inicio</Label>
              <Input
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                data-testid="filter-start-date"
              />
            </div>
            <div className="space-y-2">
              <Label>Fecha Fin</Label>
              <Input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                data-testid="filter-end-date"
              />
            </div>
            <div className="space-y-2">
              <Label>Nº Factura</Label>
              <Input
                placeholder="INV-000001"
                value={filters.invoice_number}
                onChange={(e) => handleFilterChange('invoice_number', e.target.value)}
                data-testid="filter-invoice-number"
              />
            </div>
            <div className="space-y-2">
              <Label>Doc. Cliente</Label>
              <Input
                placeholder="Documento"
                value={filters.client_document}
                onChange={(e) => handleFilterChange('client_document', e.target.value)}
                data-testid="filter-client-document"
              />
            </div>
            <div className="space-y-2">
              <Label>Usuario</Label>
              <Input
                placeholder="Email vendedor"
                value={filters.user_email}
                onChange={(e) => handleFilterChange('user_email', e.target.value)}
                data-testid="filter-user-email"
              />
            </div>
            <div className="space-y-2">
              <Label>Estado</Label>
              <Select
                value={filters.status || 'all'}
                onValueChange={(value) => handleFilterChange('status', value === 'all' ? '' : value)}
              >
                <SelectTrigger data-testid="filter-status">
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="completed">Completada</SelectItem>
                  <SelectItem value="returned">Devuelta</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={clearFilters} data-testid="clear-filters-btn">
              Limpiar Filtros
            </Button>
            <Button onClick={() => fetchInvoices()} data-testid="apply-filters-btn">
              <Search className="h-4 w-4 mr-2" />
              Buscar
            </Button>
          </div>
        </div>
      )}

      {/* Results Summary */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Mostrando {invoices.length} de {pagination.total} facturas</span>
        <Select
          value={String(pagination.limit)}
          onValueChange={(value) => setPagination(prev => ({ ...prev, limit: Number(value), page: 1 }))}
        >
          <SelectTrigger className="w-32" data-testid="page-limit-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="10">10 por página</SelectItem>
            <SelectItem value="20">20 por página</SelectItem>
            <SelectItem value="50">50 por página</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Invoices Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" data-testid="invoices-table">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">Nº Factura</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Fecha</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Cliente</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Vendedor</th>
                <th className="px-4 py-3 text-right text-sm font-medium">Total</th>
                <th className="px-4 py-3 text-center text-sm font-medium">Estado</th>
                <th className="px-4 py-3 text-center text-sm font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    Cargando facturas...
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No se encontraron facturas
                  </td>
                </tr>
              ) : (
                invoices.map((invoice) => (
                  <tr key={invoice.invoice_number} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-sm" data-testid={`invoice-number-${invoice.invoice_number}`}>
                      {invoice.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatDate(invoice.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium">{invoice.client_name}</div>
                      <div className="text-xs text-muted-foreground">{invoice.client_document}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {invoice.created_by}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium">
                      {formatCurrency(invoice.total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {getStatusBadge(invoice.status)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => viewInvoiceDetail(invoice)}
                          data-testid={`view-invoice-${invoice.invoice_number}`}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => downloadTicket(invoice.invoice_number)}
                          data-testid={`download-ticket-${invoice.invoice_number}`}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page === 1}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
              data-testid="prev-page-btn"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Anterior
            </Button>
            <span className="text-sm text-muted-foreground">
              Página {pagination.page} de {pagination.pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page === pagination.pages}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
              data-testid="next-page-btn"
            >
              Siguiente
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}
      </div>

      {/* Invoice Detail Modal */}
      <Dialog open={showDetail} onOpenChange={setShowDetail}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="invoice-detail-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Detalle de Factura {selectedInvoice?.invoice_number}
            </DialogTitle>
          </DialogHeader>
          
          {selectedInvoice && (
            <div className="space-y-6">
              {/* Invoice Info */}
              <div className="grid grid-cols-2 gap-4 p-4 bg-muted/30 rounded-lg">
                <div>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <Calendar className="h-3 w-3" /> Fecha
                  </p>
                  <p className="font-medium">{formatDate(selectedInvoice.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <User className="h-3 w-3" /> Vendedor
                  </p>
                  <p className="font-medium">{selectedInvoice.created_by}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Cliente</p>
                  <p className="font-medium">{selectedInvoice.client_name}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Documento</p>
                  <p className="font-medium">{selectedInvoice.client_document}</p>
                </div>
              </div>

              {/* Items Table */}
              <div>
                <h4 className="font-medium mb-2">Productos</h4>
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 text-left">Producto</th>
                        <th className="px-3 py-2 text-right">Cant</th>
                        <th className="px-3 py-2 text-right">Precio</th>
                        <th className="px-3 py-2 text-right">IVA</th>
                        <th className="px-3 py-2 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {selectedInvoice.items.map((item, idx) => (
                        <tr key={idx}>
                          <td className="px-3 py-2">
                            <div>{item.product_name}</div>
                            <div className="text-xs text-muted-foreground">{item.barcode}</div>
                          </td>
                          <td className="px-3 py-2 text-right">{item.quantity}</td>
                          <td className="px-3 py-2 text-right font-mono">{formatCurrency(item.unit_price)}</td>
                          <td className="px-3 py-2 text-right font-mono">{formatCurrency(item.tax_amount)}</td>
                          <td className="px-3 py-2 text-right font-mono font-medium">{formatCurrency(item.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Totals */}
              <div className="flex justify-end">
                <div className="w-64 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Subtotal:</span>
                    <span className="font-mono">{formatCurrency(selectedInvoice.subtotal)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">IVA Total:</span>
                    <span className="font-mono">{formatCurrency(selectedInvoice.total_tax)}</span>
                  </div>
                  <div className="flex justify-between text-lg font-bold border-t border-border pt-2">
                    <span>Total:</span>
                    <span className="font-mono">{formatCurrency(selectedInvoice.total)}</span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4 border-t border-border">
                <Button variant="outline" onClick={() => setShowDetail(false)}>
                  Cerrar
                </Button>
                <Button onClick={() => downloadTicket(selectedInvoice.invoice_number)} data-testid="download-ticket-modal-btn">
                  <Download className="h-4 w-4 mr-2" />
                  Descargar Ticket PDF
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Invoices;
