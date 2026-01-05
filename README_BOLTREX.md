# Boltrex - Sistema de Gestión de Inventario y Ventas

Sistema completo de gestión de inventario y ventas basado en arquitectura API REST (API-first), diseñado para pequeñas y medianas empresas.

## 🚀 Características Principales

### Autenticación y Seguridad
- Sistema de autenticación basado en JWT
- Gestión de roles de usuario (administrador, vendedor, supervisor)
- Control de permisos por rol

### Gestión de Productos
- Código de barras único por producto
- Categorización de productos
- Múltiples precios de venta por producto
- Listas de precios personalizables
- Control de IVA parametrizable

### Gestión de Clientes
- Tipos de documento parametrizables (CC, NIT, CE, Pasaporte)
- Información completa de contacto
- Geolocalización (latitud y longitud)
- Asignación de listas de precios específicas

### Sistema POS (Punto de Venta)
- Interfaz intuitiva para ventas rápidas
- Búsqueda de productos por código o nombre
- Búsqueda y selección de clientes
- Cálculo automático de precios según lista del cliente
- Cálculo automático de IVA
- Consecutivo automático de facturas
- Vista de carrito en tiempo real

### Gestión de Inventario
- Control de stock en tiempo real
- Historial completo de movimientos:
  - Compras
  - Ventas
  - Devoluciones
  - Ajustes
- Actualización automática de inventario
- Alertas de productos bajo stock

### Compras y Proveedores
- Registro de proveedores
- Gestión de compras con múltiples items
- Actualización automática de inventario al registrar compras
- Historial de compras por proveedor

### Devoluciones
- Consulta de facturas emitidas
- Devoluciones parciales o totales
- Modificación de cantidades devueltas
- Actualización automática del inventario
- Registro en historial de movimientos

### Reportes
- Reporte de ventas con filtros por fecha
- Reporte de inventario valorizado
- Exportación a CSV (Excel compatible)
- Estadísticas del dashboard

## 🛠️ Stack Tecnológico

### Backend
- **FastAPI** - Framework web moderno y de alto rendimiento
- **MongoDB** - Base de datos NoSQL
- **Motor** - Driver asíncrono de MongoDB
- **JWT** - Autenticación segura
- **Pydantic** - Validación de datos

### Frontend
- **React** - Librería de interfaces de usuario
- **React Router** - Navegación
- **Shadcn/UI** - Componentes de UI
- **Tailwind CSS** - Estilos
- **Axios** - Cliente HTTP
- **Lucide React** - Iconos

## 📁 Estructura del Proyecto

```
/app
├── backend/
│   ├── server.py          # API REST completa
│   ├── requirements.txt   # Dependencias Python
│   └── .env              # Variables de entorno
├── frontend/
│   ├── src/
│   │   ├── pages/        # Páginas de la aplicación
│   │   ├── components/   # Componentes reutilizables
│   │   ├── App.js        # Componente principal
│   │   └── index.css     # Estilos globales
│   ├── package.json      # Dependencias Node.js
│   └── .env             # Variables de entorno
└── scripts/
    └── seed_data.py      # Script para datos iniciales
```

## 🔌 API Endpoints

### Autenticación
- `POST /api/auth/register` - Registro de usuario
- `POST /api/auth/login` - Inicio de sesión
- `GET /api/auth/me` - Información del usuario actual

### Productos
- `GET /api/products` - Listar productos (con búsqueda)
- `POST /api/products` - Crear producto
- `GET /api/products/{barcode}` - Obtener producto
- `PUT /api/products/{barcode}` - Actualizar producto
- `DELETE /api/products/{barcode}` - Eliminar producto

### Categorías
- `GET /api/categories` - Listar categorías
- `POST /api/categories` - Crear categoría
- `PUT /api/categories/{name}` - Actualizar categoría
- `DELETE /api/categories/{name}` - Eliminar categoría

### Clientes
- `GET /api/clients` - Listar clientes (con búsqueda)
- `POST /api/clients` - Crear cliente
- `GET /api/clients/{document_number}` - Obtener cliente
- `PUT /api/clients/{document_number}` - Actualizar cliente

### Proveedores
- `GET /api/suppliers` - Listar proveedores
- `POST /api/suppliers` - Crear proveedor

### Facturas (POS)
- `GET /api/invoices` - Listar facturas
- `POST /api/invoices` - Crear factura
- `GET /api/invoices/{invoice_number}` - Obtener factura

### Compras
- `GET /api/purchases` - Listar compras
- `POST /api/purchases` - Registrar compra

### Devoluciones
- `GET /api/returns` - Listar devoluciones
- `POST /api/returns` - Registrar devolución

### Inventario
- `GET /api/inventory` - Consultar inventario
- `GET /api/inventory/movements` - Movimientos de inventario

### Reportes
- `GET /api/reports/sales` - Reporte de ventas
- `GET /api/reports/inventory` - Reporte de inventario

### Dashboard
- `GET /api/dashboard/stats` - Estadísticas generales

## 🎨 Diseño

El sistema utiliza un tema oscuro minimalista con las siguientes características:

- **Tipografía**:
  - Outfit - Encabezados
  - Manrope - Texto general
  - JetBrains Mono - Datos numéricos y códigos

- **Colores**:
  - Fondo: `#09090b` (zinc-950)
  - Primer plano: `#fafafa` (blanco)
  - Acentos: Escala de grises con alto contraste

- **Layout**:
  - Sidebar fijo de 240px
  - Grid responsive "Control Room" para dashboard
  - Vista dividida 60/40 para POS

## 🚀 Inicio Rápido

### Configuración Inicial

1. El sistema ya está configurado y corriendo en el ambiente
2. Datos iniciales ya creados:
   - 5 categorías (Electrónica, Alimentos, Bebidas, Hogar, Otros)
   - 4 tipos de documento (CC, NIT, CE, Pasaporte)
   - 3 listas de precios (default, mayorista, minorista)
   - 1 tasa de IVA activa (19%)

### Primer Usuario

Para crear tu primer usuario, visita la página de login y selecciona "Registrarse":

```json
{
  "email": "admin@tuempresa.com",
  "password": "tu_contraseña_segura",
  "full_name": "Tu Nombre",
  "role": "admin"
}
```

### Flujo Básico de Uso

1. **Login** - Inicia sesión con tus credenciales
2. **Crear Productos** - Define tu catálogo de productos con precios
3. **Registrar Clientes** - Agrega tus clientes con su información
4. **Registrar Proveedores** - Agrega proveedores para gestionar compras
5. **Registrar Compras** - Ingresa productos al inventario
6. **Usar POS** - Realiza ventas desde el punto de venta
7. **Ver Reportes** - Analiza tus ventas e inventario

## 📊 Características de Negocio

### Listas de Precios
- Cada producto puede tener múltiples precios
- Cada cliente tiene una lista de precios asignada
- El sistema aplica automáticamente el precio correcto en el POS

### Control de Inventario
- El stock se actualiza automáticamente en cada operación:
  - ✅ Compras: Aumentan el stock
  - ✅ Ventas: Disminuyen el stock
  - ✅ Devoluciones: Aumentan el stock
- Alertas visuales para productos bajo stock (< 10 unidades)
- Historial completo de movimientos con referencia

### Facturación
- Consecutivo automático (INV-000001, INV-000002, etc.)
- Cálculo automático de subtotal, IVA y total
- Registro del usuario que crea la factura
- Búsqueda de facturas por número o cliente

### Reportes Exportables
- Formato CSV compatible con Excel
- Filtros por rango de fechas
- Resúmenes con totales y estadísticas
- Detalle completo de transacciones

## 🔒 Seguridad

- Autenticación JWT con tokens de 24 horas
- Todas las rutas protegidas requieren autenticación
- Las contraseñas se almacenan hasheadas con bcrypt
- Validación de datos con Pydantic
- CORS configurado para producción

## 📱 Responsive Design

El sistema es completamente responsive y se adapta a:
- Desktop (1920px+)
- Laptop (1024px+)
- Tablet (768px+)
- Mobile (< 768px)

## 🔄 Integración

El sistema está diseñado con arquitectura API-first, lo que permite:
- Integración con aplicaciones móviles
- Integración con otros sistemas ERP
- Desarrollo de plugins y extensiones
- Automatizaciones via API

## 📝 Notas Importantes

- Todos los precios se manejan con 2 decimales
- Las fechas se almacenan en formato ISO 8601
- Los códigos de barras deben ser únicos
- El IVA se calcula como porcentaje del subtotal
- Los documentos de clientes deben ser únicos por tipo

## 🎯 Próximas Mejoras Recomendadas

1. **Exportación de reportes a PDF** - Facturas y reportes en formato PDF
2. **Múltiples monedas** - Soporte para diferentes monedas
3. **Imágenes de productos** - Carga y gestión de imágenes
4. **Códigos QR** - Generación de códigos QR para productos
5. **Notificaciones** - Alertas por email o SMS
6. **Descuentos y promociones** - Sistema de descuentos configurables
7. **Roles y permisos avanzados** - Control granular de accesos
8. **Auditoría completa** - Logs detallados de todas las acciones
9. **Backup automático** - Respaldos programados de la base de datos
10. **Dashboard avanzado** - Gráficos y métricas en tiempo real

## 🐛 Solución de Problemas

### El backend no responde
```bash
sudo supervisorctl restart backend
```

### El frontend no carga
```bash
sudo supervisorctl restart frontend
```

### Verificar logs del backend
```bash
tail -f /var/log/supervisor/backend.err.log
```

### Verificar logs del frontend
```bash
tail -f /var/log/supervisor/frontend.err.log
```

## 📞 Soporte

Sistema desarrollado con Emergent.sh

---

**Versión**: 1.0.0  
**Última actualización**: Enero 2025
