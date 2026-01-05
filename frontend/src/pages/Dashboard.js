import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Package, Users, FileText, DollarSign, AlertTriangle } from 'lucide-react';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-12">Cargando estadísticas...</div>;
  }

  const statCards = [
    {
      title: 'Total Productos',
      value: stats?.total_products || 0,
      icon: Package,
      color: 'text-chart-1'
    },
    {
      title: 'Total Clientes',
      value: stats?.total_clients || 0,
      icon: Users,
      color: 'text-chart-2'
    },
    {
      title: 'Facturas Emitidas',
      value: stats?.total_invoices || 0,
      icon: FileText,
      color: 'text-chart-3'
    },
    {
      title: 'Ventas Totales',
      value: `$${(stats?.total_sales || 0).toLocaleString('es-ES', { minimumFractionDigits: 2 })}`,
      icon: DollarSign,
      color: 'text-chart-1',
      mono: true
    },
    {
      title: 'Productos Bajo Stock',
      value: stats?.low_stock_products || 0,
      icon: AlertTriangle,
      color: 'text-chart-4'
    }
  ];

  return (
    <div data-testid="dashboard-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">Vista general del sistema</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, index) => (
          <Card key={index} className="card-hover" data-testid={`stat-card-${index}`}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-5 w-5 ${stat.color}`} strokeWidth={1.5} />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold tracking-tight ${stat.mono ? 'font-mono' : ''}`}>
                {stat.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8">
        <Card>
          <CardHeader>
            <CardTitle>Resumen de Operaciones</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Sistema de gestión de inventario y ventas completamente funcional.
              Utiliza el menú lateral para acceder a las diferentes secciones.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;