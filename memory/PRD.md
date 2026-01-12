# Boltrex - Sistema de Inventario y Ventas POS

## Información General
- **Nombre del Proyecto:** Boltrex
- **Tipo:** Aplicación web de gestión de inventario y ventas
- **Arquitectura:** API-first (FastAPI + React + MongoDB)
- **Tema:** Modo oscuro
- **Idioma:** Español

## Requisitos del Producto

### Módulos Core Implementados ✅
1. **Autenticación & RBAC**
   - Login JWT
   - Sistema de roles y permisos granulares
   - Gestión de usuarios extendida

2. **Gestión de Productos**
   - CRUD completo
   - Código de barras, categorías
   - Múltiples listas de precios

3. **Gestión de Categorías**
   - CRUD completo

4. **Gestión de Clientes**
   - CRUD con tipos de documento
   - Geolocalización (lat/long)
   - Lista de precios asignada

5. **Proveedores**
   - CRUD completo

6. **Compras**
   - Registro de compras
   - Actualización automática de inventario

7. **POS (Punto de Venta)**
   - Creación de facturas
   - Numeración consecutiva automática
   - Cálculo de impuestos

8. **Devoluciones**
   - Devoluciones parciales/totales
   - Actualización automática de inventario

9. **Inventario**
   - Control de stock en tiempo real
   - Historial de movimientos

10. **Reportes**
    - Ventas con filtros
    - Inventario
    - Exportación CSV/Excel

11. **Importación de Datos**
    - CSV/Excel para clientes, productos, categorías, proveedores

12. **Tasas de IVA**
    - Gestión de tasas con activación única

### Módulos Nuevos (Enero 2026) ✅
13. **Listado de Facturas POS** ✅
    - Endpoint: `GET /api/pos/invoices`
    - Filtros: fecha, cliente, usuario, número, estado
    - Paginación
    - Modal de detalle
    - Frontend: `/invoices`

14. **Generación de Tickets PDF** ✅
    - Endpoint: `GET /api/pos/invoices/{invoice_number}/ticket`
    - Formato térmico 58mm/80mm
    - Incluye: encabezado empresa, items, totales, pie de página

15. **Configuración de Tickets** ✅
    - Endpoints: `GET/PUT /api/ticket-config`
    - Campos: nombre empresa, NIT, teléfono, email, dirección
    - Ancho papel: 58mm o 80mm
    - Mensaje pie de página personalizable
    - Frontend: `/ticket-config`

## Estado de Implementación

### Completado
| Módulo | Backend | Frontend | Tests |
|--------|---------|----------|-------|
| Auth & RBAC | ✅ | ✅ | ✅ |
| Productos | ✅ | ✅ | - |
| Categorías | ✅ | ✅ | - |
| Clientes | ✅ | ✅ | - |
| Proveedores | ✅ | ✅ | - |
| Compras | ✅ | ✅ | - |
| POS | ✅ | ✅ | ✅ |
| Devoluciones | ✅ | ✅ | - |
| Inventario | ✅ | ✅ | - |
| Reportes | ✅ | ✅ | - |
| Importación | ✅ | ✅ | - |
| Facturas POS | ✅ | ✅ | ✅ |
| Tickets PDF | ✅ | ✅ | ✅ |
| Config Tickets | ✅ | ✅ | ✅ |
| Formas de Pago | ✅ | ✅ | ✅ |
| Fios (Créditos) | ✅ | ✅ | ✅ |

### Pendiente (P1)
| Tarea | Estado | Prioridad |
|-------|--------|-----------|
| Permisos UI en todas las páginas | No iniciado | P1 |

## Arquitectura

```
/app/
├── backend/
│   ├── server.py           # API principal FastAPI
│   ├── server_rbac.py      # Endpoints RBAC
│   ├── rbac.py             # Modelos y lógica RBAC
│   ├── ticket_generator.py # Generación PDF tickets
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Layout.js
│   │   │   └── ui/         # Shadcn components
│   │   ├── hooks/
│   │   │   └── usePermissions.js
│   │   └── pages/
│   │       ├── Invoices.js     # Nuevo
│   │       ├── TicketConfig.js # Nuevo
│   │       └── ...
│   └── .env
├── scripts/
│   ├── seed_data.py
│   └── init_rbac.py
└── tests/
    └── test_invoices_tickets.py
```

## Credenciales de Prueba
- **Admin:** admin@boltrex.com / admin123

## URLs
- **Frontend:** https://boltrex-inventory.preview.emergentagent.com
- **Backend API:** https://boltrex-inventory.preview.emergentagent.com/api

## Changelog

### 12 Enero 2026 - Formas de Pago y Fios
- ✅ Implementado módulo de Formas de Pago (CRUD completo)
- ✅ Implementado módulo Fios (Cuentas por cobrar y abonos parciales)
- ✅ Actualizado POS con estados de factura (pagado/por_cobrar)
- ✅ Integración de formas de pago en POS y Fios
- ✅ Tests automatizados: 25/25 passed (backend) + 20 UI tests
- ✅ Archivos nuevos:
  - `/app/frontend/src/pages/PaymentMethods.js`
  - `/app/frontend/src/pages/Fios.js`
  - `/app/tests/test_payment_methods_fios.py`

### 11 Enero 2026 - Facturas y Tickets
- ✅ Implementado módulo de listado de facturas POS con filtros y paginación
- ✅ Implementada generación de tickets PDF (58mm/80mm) con ReportLab
- ✅ Implementada configuración de tickets (empresa, formato, mensaje)
- ✅ Agregados nuevos módulos al sistema RBAC: 'invoices', 'ticket-config'
- ✅ Tests automatizados: 20/20 passed (backend) + 16 UI tests
- ✅ Archivos nuevos:
  - `/app/backend/ticket_generator.py`
  - `/app/frontend/src/pages/Invoices.js`
  - `/app/frontend/src/pages/TicketConfig.js`
  - `/app/tests/test_invoices_tickets.py`

## Próximos Pasos (Backlog)

### P1 - Alta Prioridad
1. **Implementar control de permisos UI en todas las páginas**
   - Usar hook `usePermissions` en: Categories.js, Clients.js, Suppliers.js, Purchases.js, Returns.js, UsersManagement.js, RolesPermissions.js
   - Ocultar botones Crear/Editar/Eliminar según permisos del usuario

### P2 - Media Prioridad
2. Mejorar diseño del ticket PDF (logo de empresa)
3. Agregar exportación de facturas a Excel
4. Dashboard con gráficos de ventas

### P3 - Baja Prioridad
5. Notificaciones de stock bajo
6. Integración con impresoras térmicas vía WebUSB
7. App móvil PWA
