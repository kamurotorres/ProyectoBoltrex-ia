# Prompt Maestro para Perplexity — Boltrex 2.0
## Auditoría, arquitectura objetivo y plan de reconstrucción/migración Web + Android

### INSTRUCCIÓN PRINCIPAL

Actúa como **arquitecto de software senior, consultor de producto SaaS y especialista en sistemas ERP/POS, inventarios, facturación, arquitectura multiplataforma, aplicaciones offline-first y modernización de aplicaciones existentes**.

Necesito que realices un análisis técnico y funcional profundo de **Boltrex**, una aplicación de inventario y punto de venta que **ya existe y está desarrollada**, actualmente alojada/ejecutándose en **Emergent**.

El objetivo NO es empezar a programar inmediatamente. Primero necesito un **diagnóstico objetivo del sistema actual**, un **gap analysis**, una **arquitectura objetivo** y finalmente un **plan de trabajo ejecutable** para evolucionar/reconstruir Boltrex.

La aplicación inicialmente debe funcionar en **Web**, pero debe diseñarse desde el comienzo para que posteriormente pueda ejecutarse de forma **nativa en Android**, aprovechando hardware POS y capacidades del dispositivo.

---

# 1. CONTEXTO REAL DEL PROYECTO

La aplicación existente se denomina:

**Boltrex – Inventory & POS**

La interfaz actual incluye, entre otros, los siguientes módulos:

- Dashboard
- Productos
- Categorías
- Clientes
- Proveedores
- Compras
- Devoluciones
- POS
- Facturas
- Fios (Créditos)
- Inventario
- Reportes
- Importar
- Formas de Pago
- Listas de Precios
- Usuarios
- Roles y Permisos
- Configuración de Tickets
- Configuración del Sistema

La aplicación actual ya contiene una parte importante de la lógica funcional de un sistema POS/ERP.

**No asumas que los módulos visibles en la interfaz tienen todos el mismo nivel de madurez. Debes distinguir entre funcionalidades realmente implementadas, parcialmente implementadas, superficiales o pendientes.**

---

# 2. INFORMACIÓN TÉCNICA CONOCIDA DEL SISTEMA ACTUAL

Según la documentación técnica disponible, el sistema actual utiliza:

- Backend: **FastAPI / Python**
- Frontend: **React**
- Base de datos: **MongoDB**
- Arquitectura: **API-first**

El backend está actualmente concentrado en un archivo:

```text
server.py
```

de más de 2000 líneas, donde se mezclan responsabilidades como:

- Modelos
- Conexión a base de datos
- Rutas/API
- Lógica de negocio
- Operaciones de persistencia
- Configuración

Esto constituye una deuda técnica importante.

---

# 3. FUNCIONALIDADES QUE YA EXISTEN

Según el estado documentado de Boltrex v1, ya existen:

### Seguridad

- Autenticación
- Usuarios
- RBAC
- Roles
- Permisos

### Catálogos

- Productos
- Categorías
- Clientes
- Proveedores

### Precios

- Listas de precios dinámicas

### Compras

- Proveedores
- Compras
- Estado Borrador
- Estado Confirmado

### Inventario

- Gestión de inventario
- Operaciones derivadas de compras, ventas y devoluciones

### POS

- Punto de venta
- Ventas
- Facturación
- Generación de tickets PDF
- Formatos 58 mm y 80 mm

### Devoluciones

- Gestión de devoluciones

### Crédito / Fios

- Crédito a clientes
- Registro de Fios
- Abonos
- Saldos pendientes

### Pagos

- Métodos de pago

### Administración

- Factory Reset
- Reseed de base de datos

---

# 4. DECISIÓN PREVIA DEL PROYECTO

Existe una propuesta preliminar que plantea:

- Migrar de MongoDB a PostgreSQL.
- Mantener FastAPI/Python.
- Utilizar una arquitectura backend modular.
- Utilizar Flutter para Web + Android.
- Implementar soporte offline.
- Diseñar API versionada.
- Preparar el sistema para futuras capacidades multi-sucursal/multi-tenant.

Sin embargo, **NO des por correctas estas decisiones automáticamente**.

Quiero que las revises críticamente.

Para cada decisión debes indicar:

1. Si la mantienes.
2. Si la modificas.
3. Si la descartas.
4. Por qué.
5. Qué riesgos introduce.
6. Qué alternativa existe.

---

# 5. PRIMERA ETAPA: AUDITORÍA DEL SISTEMA EXISTENTE

Antes de plantear el roadmap, realiza un diagnóstico.

Analiza:

## Backend

- Arquitectura actual.
- Acoplamiento.
- Tamaño y responsabilidades de `server.py`.
- Separación de responsabilidades.
- Modelos.
- Servicios.
- Repositorios.
- Rutas.
- Validaciones.
- Manejo de errores.
- Transacciones.
- Concurrencia.
- Seguridad.
- Escalabilidad.
- Testabilidad.

## API

Evalúa:

- Diseño de endpoints.
- Convenciones.
- Versionamiento.
- Validaciones.
- Errores.
- Autenticación.
- Autorización.
- Paginación.
- Filtros.
- Ordenamiento.
- Idempotencia.
- Documentación OpenAPI.
- Compatibilidad futura con Android.

## MongoDB

Evalúa específicamente si MongoDB debe:

- Mantenerse.
- Migrarse a PostgreSQL.
- Utilizarse temporalmente.
- Utilizarse junto con otra solución.

Analiza:

- Integridad de datos.
- Relaciones.
- Transacciones.
- Índices.
- Agregaciones.
- `$group`
- `$facet`
- `$lookup`
- `$sort`
- Crecimiento de colecciones.
- Consistencia de stock.
- Facturas.
- Pagos.
- Créditos.
- Reportes.

NO recomiendes PostgreSQL simplemente porque sea relacional. Explica técnicamente si el dominio de Boltrex realmente justifica la migración.

## Frontend React

Evalúa:

- Arquitectura.
- Componentización.
- Estado.
- Servicios.
- API client.
- Formularios.
- Validaciones.
- Manejo de permisos.
- Reutilización.
- Mantenibilidad.
- Escalabilidad.

## Testing

Determina el nivel actual de:

- Unit testing.
- Integration testing.
- API testing.
- E2E.
- Performance testing.
- Security testing.
- CI/CD.

La documentación actual indica que no existe una estrategia automatizada documentada. Verifica cómo debería corregirse esto.

---

# 6. IMPORTANTE: LA APLICACIÓN ESTÁ ALOJADA EN EMERGENT

Ten en cuenta que el sistema actual se encuentra alojado/desarrollado en **Emergent**.

Analiza las implicaciones prácticas de esto para:

- Arquitectura.
- Repositorio.
- Base de datos.
- Variables de entorno.
- Deploy.
- CI/CD.
- Backups.
- Migración.
- Portabilidad.
- Dependencia del proveedor.
- Desarrollo local.
- Staging.
- Producción.
- Publicación futura de Android.

Determina qué debe quedar desacoplado de Emergent para evitar **vendor lock-in**.

Propón una estrategia para que Boltrex pueda eventualmente desplegarse en infraestructura convencional/cloud sin depender de Emergent.

No asumas capacidades específicas de Emergent que no hayas podido verificar.

Si necesitas información actualizada sobre Emergent, investígala en fuentes oficiales o confiables y diferencia claramente:

- Información confirmada.
- Recomendación arquitectónica.
- Suposición pendiente de validar.

---

# 7. OBJETIVO DE BOLTREX 2.0

La arquitectura objetivo debe permitir:

### Web

Administración completa:

- Dashboard
- Productos
- Inventario
- Compras
- Clientes
- Proveedores
- Facturación
- Créditos
- Reportes
- Usuarios
- Roles
- Configuración

### Android

Enfocado inicialmente en operación:

- POS
- Inventario
- Escaneo de productos
- Clientes
- Créditos/Fios
- Ventas
- Devoluciones
- Consulta de stock
- Impresión de tickets
- Operación offline

### Futuro

- iOS
- Multi-sucursal
- Multi-tenant
- SaaS
- Sincronización avanzada
- Integración con hardware POS

---

# 8. DECISIÓN MULTIPLATAFORMA

Compara técnicamente:

### A. Flutter

### B. React + React Native + Expo

### C. React + Capacitor/Ionic

### D. Otra alternativa que recomiendes

Evalúa:

- Web.
- Android.
- iOS.
- Rendimiento.
- UX.
- Reutilización de código.
- Hardware.
- Impresoras térmicas.
- Bluetooth.
- Escáner.
- Cámara.
- Offline.
- SQLite.
- Sincronización.
- Mantenimiento.
- Curva de aprendizaje.
- Ecosistema.
- Testing.
- Costos de desarrollo.

Finalmente recomienda una alternativa.

**No elijas Flutter automáticamente porque aparezca en la propuesta previa.**

---

# 9. ARQUITECTURA OBJETIVO

Compara:

- Modular Monolith.
- Clean Architecture.
- Hexagonal Architecture.
- DDD.
- Microservicios.

Recomienda una arquitectura concreta.

Evalúa especialmente:

> **Modular Monolith + API-first + separación de capas + frontend/móvil desacoplados**

Explica por qué sería o no adecuada.

Evita introducir microservicios si no existe una necesidad real.

---

# 10. ESTRUCTURA DEL PROYECTO

Diseña una estructura profesional.

Evalúa el uso de un **monorepo**.

La estructura podría contener conceptualmente:

```text
boltrex/
├── apps/
│   ├── web/
│   └── mobile/
├── backend/
├── packages/
├── database/
├── infrastructure/
├── tests/
├── docs/
└── ...
```

Pero NO copies esta estructura literalmente.

Diseña la estructura definitiva recomendada.

Debe quedar claramente separado:

- Aplicación Web.
- Aplicación Mobile.
- Backend.
- API.
- Dominio.
- Aplicación.
- Infraestructura.
- Persistencia.
- Shared.
- Testing.
- CI/CD.
- Documentación.

---

# 11. BACKEND MODULAR

Define cómo evolucionar:

```text
server.py
```

hacia módulos.

Como mínimo evalúa:

```text
auth
products
categories
customers
suppliers
purchases
sales
pos
invoices
returns
inventory
credits
payments
price_lists
reports
imports
users
roles
permissions
ticket_config
system_config
audit
sync
```

Separa claramente:

- API/routers.
- Application services.
- Domain.
- Repositories.
- Infrastructure.
- Database.
- Schemas/DTOs.
- Configuración.
- Seguridad.

---

# 12. MODELO DE DATOS

Define un modelo conceptual.

Entidades mínimas:

- Product
- Category
- Customer
- Supplier
- Purchase
- PurchaseItem
- Sale
- SaleItem
- Invoice
- Inventory
- InventoryMovement
- Return
- Payment
- PaymentMethod
- Credit/Fio
- CreditPayment
- PriceList
- PriceListItem
- User
- Role
- Permission
- AuditLog
- TicketConfiguration
- SystemConfiguration

Evalúa adicionalmente:

- Branch/Sucursal.
- CashRegister/Caja.
- CashSession.
- Company/Tenant.
- Device.
- SyncEvent.
- Notification.

No significa que deban implementarse inmediatamente. Determina cuáles conviene preparar desde el modelo inicial.

---

# 13. INVENTARIO: PUNTO CRÍTICO

Evalúa que el inventario no dependa únicamente de actualizar un campo de stock.

Diseña conceptualmente:

```text
Compra
Venta
Devolución
Ajuste
Transferencia
        ↓
Inventory Movement
        ↓
Stock
```

Debe existir trazabilidad.

Determina cómo manejar:

- Ajustes.
- Devoluciones.
- Ventas concurrentes.
- Productos agotados.
- Stock negativo.
- Reservas.
- Correcciones.
- Auditoría.
- Inventario futuro por sucursal.

---

# 14. POS Y OFFLINE-FIRST

Este punto es fundamental.

Diseña una estrategia para que Android pueda vender incluso sin Internet.

Analiza:

- Base local.
- SQLite/Drift u otra alternativa.
- Cola de operaciones.
- Identificadores locales.
- Idempotencia.
- Sincronización.
- Resolución de conflictos.
- Inventario.
- Créditos.
- Pagos.
- Facturación.
- Reintentos.
- Estados de sincronización.

Especialmente analiza:

> ¿Qué sucede si dos dispositivos venden el mismo producto mientras uno está offline?

Define una estrategia realista.

No asumas que "timestamp gana" siempre es suficiente.

---

# 15. CUENTAS POR COBRAR / FIOS

Diseña correctamente:

- Crédito.
- Abonos.
- Saldo.
- Fecha de vencimiento.
- Estado.
- Mora.
- Historial.

Estados posibles:

```text
Pendiente
Parcial
Pagado
Vencido
```

Aging:

```text
0–30
31–60
61–90
90+
```

Evalúa:

- Alertas.
- Recordatorios.
- Estado de cuenta.
- Historial.
- Reportes.
- Notificaciones.

---

# 16. DASHBOARD Y REPORTES

Define los KPIs indispensables.

### Ventas

- Ventas del día.
- Ventas del mes.
- Ventas por período.
- Número de transacciones.
- Ticket promedio.
- Productos más vendidos.
- Categorías.
- Clientes.
- Métodos de pago.

### Inventario

- Stock.
- Stock bajo.
- Agotados.
- Rotación.
- Valor del inventario.
- Baja rotación.

### Rentabilidad

- Ventas.
- Costos.
- Margen bruto.
- Margen por producto.
- Margen por categoría.

### Crédito

- Cartera total.
- Vencida.
- Clientes con mayor deuda.
- Abonos.
- Aging.

Determina cuáles métricas pueden calcularse en tiempo real y cuáles deben materializarse.

---

# 17. CONTROL DE CAJA

Determina si falta un módulo de:

- Apertura de caja.
- Cierre.
- Arqueo.
- Ingresos.
- Egresos.
- Diferencias.
- Historial.
- Usuario responsable.
- Conciliación por método de pago.

Evalúa su prioridad respecto al Dashboard.

---

# 18. AUDITORÍA

Evalúa un sistema de auditoría.

Debe poder registrar:

- Usuario.
- Acción.
- Fecha/hora.
- Entidad.
- Registro afectado.
- Valor anterior.
- Valor nuevo.
- Dispositivo.
- Sucursal.
- Motivo cuando corresponda.

Priorizar especialmente:

- Inventario.
- Precios.
- Ventas.
- Devoluciones.
- Créditos.
- Pagos.
- Usuarios.

---

# 19. MULTI-SUCURSAL Y MULTI-TENANT

Aunque inicialmente Boltrex pueda operar con un único negocio y una sola sucursal, analiza si la arquitectura debe quedar preparada para:

```text
Tenant/Empresa
    ↓
Sucursal
    ↓
Caja
    ↓
Usuario
    ↓
Inventario
```

Determina qué conviene implementar ahora y qué únicamente preparar arquitectónicamente.

---

# 20. IMPORTACIÓN Y EXPORTACIÓN

Evalúa:

- Excel.
- CSV.
- PDF.

Para:

- Productos.
- Clientes.
- Proveedores.
- Inventario.
- Ventas.
- Compras.
- Cartera.
- Reportes.

Considera validación, errores de importación, archivos grandes y trazabilidad.

---

# 21. NOTIFICACIONES

Evalúa:

- Stock bajo.
- Producto agotado.
- Crédito próximo a vencer.
- Crédito vencido.
- Compras pendientes.
- Eventos administrativos.

Diferencia:

- Web notifications.
- Email.
- Push Android.
- Notificaciones internas.

---

# 22. QA Y AUTOMATIZACIÓN

Diseña una estrategia desde el inicio.

### Backend

- Pytest.
- API tests.
- Integration tests.

### Web

- Playwright.
- Selenium si realmente aporta valor.

### Mobile

- Appium u otra alternativa.
- Android E2E.

### API

- Postman/Newman u otra solución.

### Performance

- k6.

### Cross-browser/device

- BrowserStack u otra alternativa.

No necesitas utilizar todas las herramientas.

Propón un stack coherente y explica qué cubre cada herramienta.

Define también:

```text
tests/
├── unit/
├── integration/
├── api/
├── e2e/
├── performance/
└── mobile/
```

o la estructura que consideres mejor.

---

# 23. CI/CD

Diseña:

```text
Development
↓
Pull Request
↓
Automated Tests
↓
Build
↓
Staging
↓
Acceptance
↓
Production
```

Incluye:

- Git.
- Branching.
- Code review.
- Lint.
- Type checking.
- Tests.
- Security scanning.
- Build.
- Deploy.
- Rollback.
- Backup.
- Monitoring.
- Logging.

---

# 24. MIGRACIÓN DE BOLTREX V1 A V2

Este punto debe analizarse con mucho cuidado.

Compara:

### Opción A
Refactorizar progresivamente el sistema actual.

### Opción B
Reescribir completamente.

### Opción C
Strangler Pattern / migración gradual.

Determina cuál es la opción adecuada.

Si recomiendas reescritura, explica cómo evitar perder:

- Datos.
- Reglas de negocio.
- Funcionalidades.
- Historial.
- Facturas.
- Créditos.
- Inventario.

Si recomiendas migración gradual, define qué módulos migrar primero.

---

# 25. CONFLICTO IMPORTANTE A RESOLVER

Existe una propuesta previa que dice:

> "Reescritura completa desde cero"

pero también propone una fase donde el backend actual se modulariza antes de migrar.

Analiza esta aparente contradicción.

Determina si conviene:

- Refactorizar el backend actual como puente.
- Utilizarlo únicamente como fuente de conocimiento.
- Migrar directamente a una nueva arquitectura.
- Hacer un enfoque híbrido.

Explica la decisión.

---

# 26. ESTRATEGIA PARA EMERGENT

Diseña el plan considerando que el sistema actual está en Emergent.

Define:

1. Qué debe mantenerse.
2. Qué debe exportarse.
3. Cómo proteger los datos.
4. Cómo obtener un repositorio independiente.
5. Cómo separar configuración de código.
6. Cómo separar producción y staging.
7. Cómo realizar backups.
8. Cómo preparar la migración.
9. Cómo reducir dependencia de Emergent.
10. Qué partes pueden continuar alojadas allí temporalmente.

El objetivo es que Boltrex sea **portable**.

---

# 27. ROADMAP

Construye un roadmap utilizando:

- P0 = Bloqueante / Arquitectura.
- P1 = Crítico.
- P2 = Alto valor.
- P3 = Mejora.
- P4 = Futuro.

No asumas que Dashboard debe ir primero.

Determina el orden correcto.

Como hipótesis inicial, evalúa:

```text
P0 Auditoría
↓
P0 Arquitectura
↓
P0 Datos / modelo
↓
P0 Refactorización
↓
P1 Seguridad + auditoría
↓
P1 Inventario / transacciones
↓
P1 POS
↓
P1 Fios / cartera
↓
P2 Dashboard / reportes
↓
P2 Caja
↓
P2 Notificaciones
↓
P2 Importación/exportación
↓
P1/P2 Mobile Android
↓
P3 Multi-sucursal
↓
P4 SaaS / Multi-tenant
```

**No tomes este orden como definitivo. Corrígelo si tu análisis demuestra que existe una secuencia mejor.**

---

# 28. MATRIZ DE PRIORIZACIÓN

Genera:

| Iniciativa | Impacto | Esfuerzo | Riesgo | Dependencias | Prioridad |
|---|---:|---:|---:|---|---|

Incluye todas las iniciativas importantes.

---

# 29. GAP ANALYSIS

Genera:

| Área | Estado actual | Problema | Estado objetivo | Acción | Prioridad |
|---|---|---|---|---|---|

Separando:

- Existe y está bien.
- Existe pero necesita refactor.
- Existe parcialmente.
- No existe.
- Debe rediseñarse.

---

# 30. ESTRUCTURA FINAL DEL DOCUMENTO

El resultado debe contener exactamente estas secciones:

## A. Resumen ejecutivo

## B. Estado actual de Boltrex

## C. Arquitectura actual

## D. Auditoría técnica

## E. Auditoría funcional

## F. Gap Analysis

## G. Arquitectura objetivo

## H. Stack tecnológico recomendado

## I. Estructura del proyecto

## J. Arquitectura backend

## K. Arquitectura Web

## L. Arquitectura Android

## M. Modelo de datos

## N. Flujos de negocio

## O. Estrategia offline/sincronización

## P. POS y hardware

## Q. Inventario

## R. Fios / cuentas por cobrar

## S. Dashboard y reporting

## T. Caja

## U. Auditoría

## V. Seguridad

## W. QA y automatización

## X. CI/CD y DevOps

## Y. Estrategia Emergent / portabilidad

## Z. Migración V1 → V2

## AA. Roadmap

## AB. Priorización

## AC. Riesgos y mitigaciones

## AD. Funcionalidades futuras

---

# 31. FORMATO DEL ROADMAP

Para cada fase indica:

### Objetivo

### Módulos

### Dependencias

### Entregables

### Criterios de aceptación

### Pruebas

### Riesgos

### Resultado esperado

---

# 32. CRITERIOS ARQUITECTÓNICOS OBLIGATORIOS

La solución final debe:

1. Ser API-first.
2. Separar frontend de backend.
3. Permitir Web + Android.
4. Evitar duplicación innecesaria.
5. Permitir offline en Android.
6. Ser testeable.
7. Ser observable.
8. Ser segura.
9. Ser escalable.
10. Ser portable fuera de Emergent.
11. Permitir evolución a multi-sucursal.
12. Poder evolucionar a SaaS.
13. Mantener trazabilidad de inventario.
14. Mantener trazabilidad financiera.
15. Evitar que la lógica crítica dependa del frontend.
16. Evitar un backend monolítico dentro de `server.py`.
17. Tener API versionada.
18. Tener estrategia de migración de datos.
19. Tener estrategia de rollback.
20. Tener una estrategia clara para conflictos offline.

---

# 33. REGLAS PARA TU RESPUESTA

No quiero:

- Código de implementación.
- SQL completo.
- Pantallas detalladas.
- Componentes visuales detallados.
- Código Flutter.
- Código React.
- Código FastAPI.

Sí quiero:

- Arquitectura.
- Decisiones.
- Diagramas conceptuales.
- Dependencias.
- Estructura.
- Modelo de datos.
- Flujos.
- Roadmap.
- Riesgos.
- Priorización.

Cada recomendación importante debe incluir:

**Problema → Alternativas → Recomendación → Justificación → Impacto.**

---

# 34. RESULTADO FINAL ESPERADO

El documento debe ser suficientemente detallado para convertirse en el:

> **BLUEPRINT TÉCNICO OFICIAL DE BOLTREX 2.0**

y posteriormente utilizarse como documento maestro para que desarrolladores humanos o agentes de IA puedan implementar el sistema **módulo por módulo**, sin tomar decisiones arquitectónicas contradictorias durante el desarrollo.

La secuencia debe ser:

**AUDITAR → ENTENDER → DEFINIR ARQUITECTURA → DEFINIR DATOS → PRIORIZAR → MIGRAR/RECONSTRUIR → PROBAR → DESPLEGAR → EVOLUCIONAR**

No empezar por "hacer pantallas".

---

# 35. PREGUNTA FINAL QUE DEBES RESPONDER

Al finalizar, entrega una recomendación ejecutiva de máximo 1 página respondiendo:

1. ¿Conviene mantener FastAPI?
2. ¿Conviene mantener MongoDB?
3. ¿Conviene utilizar PostgreSQL?
4. ¿Conviene Flutter?
5. ¿Conviene React + React Native?
6. ¿Conviene monorepo?
7. ¿Conviene Modular Monolith?
8. ¿Debe implementarse offline desde el principio?
9. ¿Debe hacerse refactor del backend actual o reconstrucción?
10. ¿Qué debe hacerse primero?
11. ¿Qué NO debe hacerse todavía?
12. ¿Cómo reducir la dependencia de Emergent?
13. ¿Cuál es el MVP real de Boltrex 2.0?
14. ¿Cuál sería el roadmap recomendado para los próximos hitos?

Justifica cada respuesta y separa claramente hechos conocidos, recomendaciones y supuestos pendientes de validar.
