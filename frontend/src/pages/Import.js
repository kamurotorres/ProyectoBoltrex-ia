import React, { useState } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Upload, Download, FileText, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { usePermissions } from '@/hooks/usePermissions';

const Import = () => {
  const { canCreate } = usePermissions();
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [activeTab, setActiveTab] = useState('categories');

  const modules = [
    {
      id: 'categories',
      name: 'Categorías',
      description: 'Importar categorías de productos',
      icon: '📁',
      requiredColumns: ['name', 'description'],
      example: [
        { name: 'Electrónica', description: 'Dispositivos electrónicos' },
        { name: 'Alimentos', description: 'Productos alimenticios' }
      ]
    },
    {
      id: 'products',
      name: 'Productos',
      description: 'Importar productos con precios',
      icon: '📦',
      requiredColumns: ['barcode', 'name', 'category', 'purchase_price', 'tax_rate'],
      optionalColumns: ['description', 'price_default', 'price_mayorista', 'price_minorista'],
      example: [
        {
          barcode: '001',
          name: 'Producto 1',
          category: 'Electrónica',
          purchase_price: '100.00',
          tax_rate: '19',
          price_default: '150.00'
        }
      ]
    },
    {
      id: 'clients',
      name: 'Clientes',
      description: 'Importar base de clientes',
      icon: '👥',
      requiredColumns: ['document_type', 'document_number', 'first_name', 'last_name'],
      optionalColumns: ['phone', 'email', 'address', 'latitude', 'longitude', 'price_list'],
      example: [
        {
          document_type: 'CC',
          document_number: '123456789',
          first_name: 'Juan',
          last_name: 'Pérez',
          email: 'juan@example.com',
          price_list: 'default'
        }
      ]
    },
    {
      id: 'suppliers',
      name: 'Proveedores',
      description: 'Importar proveedores',
      icon: '🚚',
      requiredColumns: ['name'],
      optionalColumns: ['contact_name', 'phone', 'email', 'address'],
      example: [
        {
          name: 'Proveedor ABC',
          contact_name: 'María López',
          phone: '3001234567',
          email: 'contacto@abc.com'
        }
      ]
    }
  ];

  const handleFileUpload = async (event, moduleId) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = [
      'text/csv',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ];
    
    if (!validTypes.includes(file.type) && !file.name.endsWith('.csv') && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast.error('Tipo de archivo no válido. Use CSV o Excel (.xlsx, .xls)');
      return;
    }

    setLoading(true);
    setResults(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/import/${moduleId}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setResults(response.data);
      
      if (response.data.success > 0) {
        toast.success(`${response.data.success} registros importados exitosamente`);
      }
      if (response.data.errors.length > 0) {
        toast.warning(`${response.data.errors.length} registros con errores`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al importar archivo');
      setResults(null);
    } finally {
      setLoading(false);
      event.target.value = null; // Reset input
    }
  };

  const handleDownloadTemplate = async (moduleId) => {
    try {
      const response = await axios.get(`${API}/import/templates/${moduleId}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `plantilla_${moduleId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error al descargar plantilla');
    }
  };

  const currentModule = modules.find(m => m.id === activeTab);

  return (
    <div data-testid="import-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Importar Datos</h1>
        <p className="text-muted-foreground mt-2">
          Carga masiva de datos desde archivos CSV o Excel
        </p>
      </div>

      <Alert className="mb-6">
        <Info className="h-4 w-4" />
        <AlertTitle>Formatos Soportados</AlertTitle>
        <AlertDescription>
          Puedes importar archivos en formato CSV o Excel (.xlsx, .xls). Descarga la plantilla correspondiente para cada módulo.
        </AlertDescription>
      </Alert>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid grid-cols-4 w-full max-w-2xl">
          {modules.map((module) => (
            <TabsTrigger key={module.id} value={module.id} data-testid={`tab-${module.id}`}>
              <span className="mr-2">{module.icon}</span>
              {module.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {modules.map((module) => (
          <TabsContent key={module.id} value={module.id} className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: Upload */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span>{module.icon}</span>
                    Importar {module.name}
                  </CardTitle>
                  <CardDescription>{module.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold">Columnas Requeridas:</h4>
                    <div className="flex flex-wrap gap-2">
                      {module.requiredColumns.map((col) => (
                        <span key={col} className="text-xs px-2 py-1 bg-chart-1/20 text-chart-1 rounded">
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>

                  {module.optionalColumns && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">Columnas Opcionales:</h4>
                      <div className="flex flex-wrap gap-2">
                        {module.optionalColumns.map((col) => (
                          <span key={col} className="text-xs px-2 py-1 bg-muted text-muted-foreground rounded">
                            {col}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t pt-4 space-y-4">
                    <Button
                      variant="outline"
                      onClick={() => handleDownloadTemplate(module.id)}
                      className="w-full"
                      data-testid={`download-template-${module.id}`}
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Descargar Plantilla CSV
                    </Button>

                    <div className="relative">
                      <input
                        type="file"
                        accept=".csv,.xlsx,.xls"
                        onChange={(e) => handleFileUpload(e, module.id)}
                        className="hidden"
                        id={`file-input-${module.id}`}
                        data-testid={`file-input-${module.id}`}
                      />
                      <label htmlFor={`file-input-${module.id}`}>
                        <Button
                          type="button"
                          className="w-full"
                          disabled={loading || !canCreate('import')}
                          onClick={() => document.getElementById(`file-input-${module.id}`).click()}
                          data-testid={`upload-button-${module.id}`}
                        >
                          {loading ? (
                            <>Procesando...</>
                          ) : (
                            <>
                              <Upload className="h-4 w-4 mr-2" />
                              Seleccionar y Cargar Archivo
                            </>
                          )}
                        </Button>
                      </label>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Right Column: Instructions */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Instrucciones
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-3 text-sm">
                    <div>
                      <h4 className="font-semibold mb-1">1. Descarga la Plantilla</h4>
                      <p className="text-muted-foreground">
                        Obtén la plantilla CSV con las columnas correctas y ejemplos de datos.
                      </p>
                    </div>

                    <div>
                      <h4 className="font-semibold mb-1">2. Completa tus Datos</h4>
                      <p className="text-muted-foreground">
                        Abre el archivo en Excel o cualquier editor de hojas de cálculo y completa con tus datos.
                      </p>
                    </div>

                    <div>
                      <h4 className="font-semibold mb-1">3. Verifica las Columnas</h4>
                      <p className="text-muted-foreground">
                        Asegúrate de que las columnas requeridas estén completas y que los datos sean válidos.
                      </p>
                    </div>

                    <div>
                      <h4 className="font-semibold mb-1">4. Importa el Archivo</h4>
                      <p className="text-muted-foreground">
                        Selecciona y carga tu archivo. El sistema validará y procesará los datos.
                      </p>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-semibold mb-2 text-sm">Ejemplo de Datos:</h4>
                    <div className="bg-muted p-3 rounded-md overflow-x-auto">
                      <pre className="text-xs">
                        {JSON.stringify(module.example[0], null, 2)}
                      </pre>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Results Section */}
            {results && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {results.errors.length === 0 ? (
                      <CheckCircle className="h-5 w-5 text-chart-1" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-chart-3" />
                    )}
                    Resultados de la Importación
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 bg-chart-1/10 rounded-md">
                      <p className="text-sm text-muted-foreground">Exitosos</p>
                      <p className="text-2xl font-bold text-chart-1" data-testid="success-count">{results.success}</p>
                    </div>
                    <div className="p-4 bg-chart-4/10 rounded-md">
                      <p className="text-sm text-muted-foreground">Con Errores</p>
                      <p className="text-2xl font-bold text-chart-4" data-testid="error-count">{results.errors.length}</p>
                    </div>
                    <div className="p-4 bg-muted rounded-md">
                      <p className="text-sm text-muted-foreground">Total</p>
                      <p className="text-2xl font-bold" data-testid="total-count">{results.total}</p>
                    </div>
                  </div>

                  {results.errors.length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-3">Errores Detectados:</h4>
                      <div className="border rounded-md max-h-96 overflow-y-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-24">Fila</TableHead>
                              <TableHead>Error</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {results.errors.map((error, index) => (
                              <TableRow key={index} data-testid={`error-row-${index}`}>
                                <TableCell className="font-mono">{error.row}</TableCell>
                                <TableCell className="text-sm text-muted-foreground">{error.error}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default Import;
