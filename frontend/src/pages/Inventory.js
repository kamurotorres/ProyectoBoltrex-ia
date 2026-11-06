import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Search, Package, TrendingUp, TrendingDown, AlertTriangle, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePermissions } from '@/hooks/usePermissions';
import { AdjustmentDialog, AdjustmentsTab, signedMoney } from '@/components/inventory/Adjustments';
import { toast } from 'sonner';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import Pagination from '@/components/Pagination';

const Inventory = () => {
  // P1.18: stock y movimientos paginados en el servidor; los totales los calcula el servidor
  // sobre TODOS los productos (antes solo sobre los primeros 1.000).
  const [searchParams] = useSearchParams();
  const [stockFilter, setStockFilter] = useState(() => (['low', 'out'].includes(searchParams.get('stock')) ? searchParams.get('stock') : ''));
  // La campana de alertas abre Inventario con ?stock=low aunque ya se esté en esta pantalla.
  useEffect(() => {
    const s = searchParams.get('stock');
    if (s === 'low' || s === 'out') setStockFilter(s);
  }, [searchParams]);
  // P2.32: ajustes de inventario (solo con permiso inventario → crear; por defecto el Administrador).
  const { canCreate } = usePermissions();
  const canAdjust = canCreate('inventory');
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustProduct, setAdjustProduct] = useState(null);
  const [adjustRefresh, setAdjustRefresh] = useState(0);
  const openAdjust = (product = null) => { setAdjustProduct(product); setAdjustOpen(true); };
  const stockList = usePaginatedList(`${API}/inventory`, {
    params: { tz_offset_minutes: new Date().getTimezoneOffset(), ...(stockFilter ? { stock: stockFilter } : {}) },
    errorMessage: 'Error al cargar inventario',
  });
  const movementList = usePaginatedList(`${API}/inventory/movements`, { errorMessage: 'Error al cargar movimientos' });
  const loading = stockList.loading && !stockList.summary;
  const filteredProducts = stockList.items;
  const movements = movementList.items;
  const summary = stockList.summary || {};
  const totalValue = summary.total_value || 0;
  const lowStock = summary.low_stock_count || 0;
  const outOfStock = summary.out_of_stock_count || 0;
  const adjMonth = stockList.adjustments_month || {};
  const onAdjustmentSaved = () => {
    stockList.reload();
    movementList.reload();
    setAdjustRefresh((n) => n + 1);
  };

  const getMovementIcon = (type) => {
    switch (type) {
      case 'purchase':
        return <TrendingUp className="h-4 w-4 text-chart-1" />;
      case 'sale':
        return <TrendingDown className="h-4 w-4 text-chart-4" />;
      case 'return':
        return <TrendingUp className="h-4 w-4 text-chart-3" />;
      case 'adjustment':
        return <SlidersHorizontal className="h-4 w-4 text-amber-400" />;
      default:
        return <Package className="h-4 w-4" />;
    }
  };

  const getMovementLabel = (type) => {
    const labels = {
      purchase: 'Compra',
      sale: 'Venta',
      return: 'Devolución',
      adjustment: 'Ajuste'
    };
    return labels[type] || type;
  };

  if (loading) return <div className="text-center py-12">Cargando...</div>;

  return (
    <div data-testid="inventory-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Inventario</h1>
        <p className="text-muted-foreground mt-2">Control de stock en tiempo real</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        <Card data-testid="total-value-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Valor Total Inventario</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono">${totalValue.toFixed(2)}</div>
          </CardContent>
        </Card>

        <Card data-testid="low-stock-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Productos Bajo Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold flex items-center gap-2">
              <AlertTriangle className="h-8 w-8 text-chart-3" />
              {lowStock}
            </div>
          </CardContent>
        </Card>

        <Card data-testid="out-of-stock-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Sin Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold flex items-center gap-2">
              <AlertTriangle className="h-8 w-8 text-chart-4" />
              {outOfStock}
            </div>
          </CardContent>
        </Card>

        <Card data-testid="adjustments-month-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pérdidas por ajustes del mes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-red-400">${Number(adjMonth.loss_value || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 })}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {adjMonth.adjustments || 0} ajuste(s) · sobrantes ${Number(adjMonth.gain_value || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 })} · neto {signedMoney(adjMonth.net_value || 0)}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="stock" className="space-y-4">
        <TabsList>
          <TabsTrigger value="stock" data-testid="tab-stock">Stock Actual</TabsTrigger>
          <TabsTrigger value="movements" data-testid="tab-movements">Movimientos</TabsTrigger>
          <TabsTrigger value="adjustments" data-testid="tab-adjustments">Ajustes</TabsTrigger>
        </TabsList>

        <TabsContent value="stock" className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar productos..."
              value={stockList.search}
              onChange={(e) => stockList.setSearch(e.target.value)}
              className="pl-10"
              data-testid="search-inventory-input"
            />
          </div>
          <div className="flex flex-wrap gap-2" data-testid="inventory-stock-filter">
            {[['', 'Todos'], ['low', 'Bajo stock (bajo su mínimo)'], ['out', 'Agotados']].map(([value, label]) => (
              <button
                key={value || 'all'}
                type="button"
                onClick={() => setStockFilter(value)}
                className={`rounded-full border px-3 py-1 text-xs ${stockFilter === value ? 'bg-primary text-primary-foreground border-primary' : 'border-border text-muted-foreground hover:bg-muted'}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Código</TableHead>
                  <TableHead>Producto</TableHead>
                  <TableHead>Categoría</TableHead>
                  <TableHead className="text-right font-mono">Stock</TableHead>
                  <TableHead className="text-right font-mono">Mínimo</TableHead>
                  <TableHead className="text-right font-mono">P. Compra</TableHead>
                  <TableHead className="text-right font-mono">Valor Total</TableHead>
                  <TableHead className="text-center">Estado</TableHead>
                  {canAdjust && <TableHead />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProducts.map((product, index) => (
                  <TableRow key={product.barcode} data-testid={`inventory-row-${index}`}>
                    <TableCell className="font-mono">{product.barcode}</TableCell>
                    <TableCell>{product.name}</TableCell>
                    <TableCell>{product.category}</TableCell>
                    <TableCell className="text-right font-mono font-bold">{product.stock}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">
                      {product.min_stock_effective}{product.min_stock == null ? ' (general)' : ''}
                    </TableCell>
                    <TableCell className="text-right font-mono">${product.purchase_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono">${(product.purchase_price * product.stock).toFixed(2)}</TableCell>
                    <TableCell className="text-center">
                      {product.stock_status === 'out' ? (
                        <span className="text-xs px-2 py-1 rounded-full bg-destructive text-destructive-foreground">Sin Stock</span>
                      ) : product.stock_status === 'low' ? (
                        <span className="text-xs px-2 py-1 rounded-full bg-chart-3/20 text-chart-3">Bajo</span>
                      ) : (
                        <span className="text-xs px-2 py-1 rounded-full bg-chart-1/20 text-chart-1">Normal</span>
                      )}
                    </TableCell>
                    {canAdjust && (
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => openAdjust(product)} data-testid={`adjust-product-${index}`}>
                          <SlidersHorizontal className="h-4 w-4 mr-1" /> Ajustar
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination {...stockList.paginationProps} noun="producto(s)" testId="inventory-pagination" />
        </TabsContent>

        <TabsContent value="movements" className="space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por producto, código, referencia o usuario..."
              value={movementList.search}
              onChange={(e) => movementList.setSearch(e.target.value)}
              className="pl-10"
              data-testid="search-movements-input"
            />
          </div>
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Producto</TableHead>
                  <TableHead>Código</TableHead>
                  <TableHead className="text-right font-mono">Cantidad</TableHead>
                  <TableHead>Referencia</TableHead>
                  <TableHead>Usuario</TableHead>
                  <TableHead>Fecha</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movements.map((movement, index) => (
                  <TableRow key={index} data-testid={`movement-row-${index}`}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getMovementIcon(movement.movement_type)}
                        <span className="text-sm">{getMovementLabel(movement.movement_type)}</span>
                      </div>
                    </TableCell>
                    <TableCell>{movement.product_name}</TableCell>
                    <TableCell className="font-mono">{movement.barcode}</TableCell>
                    <TableCell className={`text-right font-mono font-bold ${movement.quantity > 0 ? 'text-chart-1' : 'text-chart-4'}`}>
                      {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {movement.reference || '-'}
                      {movement.reason && <div className="text-xs">{movement.reason}</div>}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{movement.created_by}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(movement.created_at).toLocaleString('es-ES')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination {...movementList.paginationProps} noun="movimiento(s)" testId="movements-pagination" />
        </TabsContent>

        <TabsContent value="adjustments" className="space-y-4">
          <AdjustmentsTab canAdjust={canAdjust} onNew={() => openAdjust(null)} refreshKey={adjustRefresh} />
        </TabsContent>
      </Tabs>

      <AdjustmentDialog open={adjustOpen} onOpenChange={setAdjustOpen} initialProduct={adjustProduct} onSaved={onAdjustmentSaved} />
    </div>
  );
};

export default Inventory;