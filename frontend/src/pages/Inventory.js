import React, { useState, useEffect } from 'react';
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
import { Search, Package, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const Inventory = () => {
  const [products, setProducts] = useState([]);
  const [movements, setMovements] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [productsRes, movementsRes] = await Promise.all([
        axios.get(`${API}/inventory`),
        axios.get(`${API}/inventory/movements`)
      ]);
      setProducts(productsRes.data);
      setMovements(movementsRes.data);
    } catch (error) {
      toast.error('Error al cargar inventario');
    } finally {
      setLoading(false);
    }
  };

  const filteredProducts = products.filter(p =>
    search === '' ||
    p.barcode.toLowerCase().includes(search.toLowerCase()) ||
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  const totalValue = products.reduce((sum, p) => sum + (p.purchase_price * p.stock), 0);
  const lowStock = products.filter(p => p.stock < 10).length;
  const outOfStock = products.filter(p => p.stock === 0).length;

  const getMovementIcon = (type) => {
    switch (type) {
      case 'purchase':
        return <TrendingUp className="h-4 w-4 text-chart-1" />;
      case 'sale':
        return <TrendingDown className="h-4 w-4 text-chart-4" />;
      case 'return':
        return <TrendingUp className="h-4 w-4 text-chart-3" />;
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
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
      </div>

      <Tabs defaultValue="stock" className="space-y-4">
        <TabsList>
          <TabsTrigger value="stock" data-testid="tab-stock">Stock Actual</TabsTrigger>
          <TabsTrigger value="movements" data-testid="tab-movements">Movimientos</TabsTrigger>
        </TabsList>

        <TabsContent value="stock" className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar productos..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
              data-testid="search-inventory-input"
            />
          </div>

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
                  <TableHead className="text-center">Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProducts.map((product, index) => (
                  <TableRow key={product.barcode} data-testid={`inventory-row-${index}`}>
                    <TableCell className="font-mono">{product.barcode}</TableCell>
                    <TableCell>{product.name}</TableCell>
                    <TableCell>{product.category}</TableCell>
                    <TableCell className="text-right font-mono font-bold">{product.stock}</TableCell>
                    <TableCell className="text-right font-mono">${product.purchase_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono">${(product.purchase_price * product.stock).toFixed(2)}</TableCell>
                    <TableCell className="text-center">
                      {product.stock === 0 ? (
                        <span className="text-xs px-2 py-1 rounded-full bg-destructive text-destructive-foreground">Sin Stock</span>
                      ) : product.stock < 10 ? (
                        <span className="text-xs px-2 py-1 rounded-full bg-chart-3/20 text-chart-3">Bajo</span>
                      ) : (
                        <span className="text-xs px-2 py-1 rounded-full bg-chart-1/20 text-chart-1">Normal</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="movements" className="space-y-4">
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
                {movements.slice(0, 100).map((movement, index) => (
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
                    <TableCell className="text-sm text-muted-foreground">{movement.reference || '-'}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{movement.created_by}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(movement.created_at).toLocaleString('es-ES')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Inventory;