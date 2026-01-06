# Guía de Uso: Sistema de Roles y Permisos - Boltrex

## 🎯 Cómo Funciona el Sistema

El sistema implementa **RBAC (Role-Based Access Control)** con las siguientes características:

### Arquitectura
```
Usuario → tiene múltiples Roles → tienen Permisos sobre Módulos → con acciones CRUD
```

### Flujo de Permisos
1. Un **Usuario** puede tener uno o varios **Roles**
2. Cada **Rol** tiene **Permisos** sobre **Módulos** específicos
3. Los permisos se definen a nivel **CRUD**: READ, CREATE, UPDATE, DELETE
4. El usuario hereda todos los permisos de TODOS sus roles (lógica OR)

## 📝 Guía de Pruebas

### Paso 1: Crear un Usuario de Prueba

1. **Cerrar sesión** si estás logueado
2. En la página de login, hacer clic en **"¿No tienes cuenta? Regístrate"**
3. Completar el formulario:
   - Email: `vendedor@test.com`
   - Contraseña: `test123`
   - Nombre completo: `Juan Vendedor`
4. El usuario se crea automáticamente con el rol **"Vendedor"**

### Paso 2: Verificar Permisos del Vendedor

**Rol Vendedor tiene acceso a:**
- ✅ Dashboard (solo lectura)
- ✅ Productos (solo lectura)
- ✅ Categorías (solo lectura)
- ✅ Clientes (lectura, crear, editar)
- ✅ POS (lectura, crear)
- ✅ Inventario (solo lectura)
- ✅ Reportes (solo lectura)

**Rol Vendedor NO tiene acceso a:**
- ❌ Proveedores
- ❌ Compras
- ❌ Devoluciones
- ❌ Importar
- ❌ Usuarios
- ❌ Roles y Permisos

**Pruebas a realizar:**

1. **Login con vendedor@test.com**
   ```
   Email: vendedor@test.com
   Contraseña: test123
   ```

2. **Verificar menú lateral**
   - Solo deben aparecer los módulos con permiso READ
   - Módulos ocultos: Proveedores, Compras, Devoluciones, Importar, Usuarios, Roles

3. **Ir a Productos**
   - ✅ Puedes ver la lista de productos
   - ❌ NO debe aparecer el botón "Nuevo Producto" (sin permiso CREATE)
   - ❌ NO deben aparecer botones de editar/eliminar (sin permisos UPDATE/DELETE)

4. **Ir a Clientes**
   - ✅ Puedes ver la lista de clientes
   - ✅ DEBE aparecer el botón "Nuevo Cliente" (tiene permiso CREATE)
   - ✅ DEBEN aparecer botones de editar (tiene permiso UPDATE)

5. **Ir a POS**
   - ✅ Puedes acceder al punto de venta
   - ✅ Puedes crear ventas (tiene permiso CREATE)

### Paso 3: Modificar Permisos del Rol Vendedor

1. **Cerrar sesión del vendedor**
2. **Login con admin@boltrex.com** (administrador)
3. Ir a **Roles y Permisos** en el menú
4. Tab **"Matriz de Permisos"**
5. Localizar la columna **"Vendedor"** y la fila **"Productos"**
6. **Activar** los permisos:
   - ✅ Click en "create" (se pondrá verde)
   - ✅ Click en "update" (se pondrá verde)
7. Los cambios se guardan automáticamente

### Paso 4: Verificar Cambios de Permisos

1. **Cerrar sesión del admin**
2. **Login nuevamente con vendedor@test.com**
3. **Ir a Productos**
4. **Verificar que ahora SÍ aparecen:**
   - ✅ Botón "Nuevo Producto"
   - ✅ Botones de editar en cada producto

### Paso 5: Asignar Múltiples Roles a un Usuario

1. **Login con admin**
2. Ir a **Usuarios** en el menú
3. Buscar **vendedor@test.com**
4. Click en el ícono de **Escudo (Shield)** en las acciones
5. En el diálogo "Asignar Roles":
   - ✅ Marcar "Vendedor"
   - ✅ Marcar "Supervisor"
6. Click en **"Asignar Roles"**

Ahora el usuario tiene permisos combinados de ambos roles (OR lógico).

### Paso 6: Verificar Permisos Combinados

1. **Cerrar sesión y login con vendedor@test.com**
2. **Verificar menú lateral** - Ahora deberían aparecer más módulos:
   - ✅ Proveedores (del rol Supervisor)
   - ✅ Compras (del rol Supervisor)
   - ✅ Devoluciones (del rol Supervisor)
3. **Ir a Proveedores**
   - ✅ Debe permitir acceso (heredado de rol Supervisor)

## 🔐 Roles por Defecto

### 1. Administrador
**Descripción:** Acceso total al sistema

**Permisos:** Todos (READ, CREATE, UPDATE, DELETE) en todos los módulos

**Usar para:** Configuración del sistema, gestión de usuarios y permisos

### 2. Vendedor
**Descripción:** Acceso a ventas y consultas

**Permisos:**
- Dashboard: READ
- Productos: READ
- Categorías: READ
- Clientes: READ, CREATE, UPDATE
- POS: READ, CREATE
- Inventario: READ
- Reportes: READ

**Usar para:** Personal de ventas y atención al cliente

### 3. Supervisor
**Descripción:** Supervisión de operaciones

**Permisos:**
- Dashboard: READ
- Productos: READ, CREATE, UPDATE
- Categorías: READ, CREATE, UPDATE
- Clientes: READ, CREATE, UPDATE
- Proveedores: READ, CREATE, UPDATE
- Compras: READ, CREATE
- Devoluciones: READ, CREATE
- POS: READ, CREATE
- Inventario: READ
- Reportes: READ

**Usar para:** Supervisores de tienda, gerentes de operaciones

## 🎨 Indicadores Visuales

### Matriz de Permisos
- **Verde con ✓**: Permiso activo
- **Gris con ✗**: Permiso inactivo
- **Opaco**: Rol o módulo inactivo (no se puede modificar)

### Badges de Estado
- **Verde "Activo"**: Usuario/Rol activo
- **Rojo "Inactivo"**: Usuario/Rol desactivado

### Menú Lateral
- **Solo aparecen** los módulos donde el usuario tiene al menos permiso READ
- **Se ocultan automáticamente** los módulos sin permisos

### Botones de Acción
- **Botón "Nuevo"**: Solo visible con permiso CREATE
- **Botón de Editar**: Solo visible con permiso UPDATE
- **Botón de Eliminar**: Solo visible con permiso DELETE

## 🛠️ Casos de Uso Comunes

### Caso 1: Empleado Solo Ventas
```
Usuario: vendedor-junior@empresa.com
Rol: Vendedor
Resultado: Solo puede ver productos y crear ventas, no puede modificar precios
```

### Caso 2: Gerente de Tienda
```
Usuario: gerente@empresa.com
Roles: Supervisor + Vendedor
Resultado: Acceso completo a operaciones, sin acceso a configuración
```

### Caso 3: Administrador del Sistema
```
Usuario: admin@empresa.com
Rol: Administrador
Resultado: Acceso total incluyendo gestión de usuarios y permisos
```

### Caso 4: Contador
```
Usuario: contador@empresa.com
Rol: Crear rol "Contador" con:
  - Reportes: READ
  - Ventas: READ
  - Inventario: READ
Resultado: Solo puede generar y exportar reportes
```

## 🔧 Cómo Crear un Rol Personalizado

1. **Login como Administrador**
2. Ir a **Roles y Permisos**
3. Tab **"Gestionar Roles"**
4. Click en **"Nuevo Rol"**
5. Completar:
   - Nombre: `Contador`
   - Descripción: `Solo reportes y consultas`
   - Estado: Activo ✓
6. Click en **"Crear Rol"**
7. Ir a tab **"Matriz de Permisos"**
8. Localizar columna **"Contador"**
9. Activar permisos según necesidad
10. Asignar rol a usuarios en módulo **Usuarios**

## 📊 Mapeo de Módulos Frontend ↔ Backend

| Ruta Frontend | Slug Backend | Descripción |
|--------------|--------------|-------------|
| `/` | `dashboard` | Panel principal |
| `/products` | `products` | Gestión de productos |
| `/categories` | `categories` | Gestión de categorías |
| `/clients` | `clients` | Gestión de clientes |
| `/suppliers` | `suppliers` | Gestión de proveedores |
| `/purchases` | `purchases` | Registro de compras |
| `/returns` | `returns` | Devoluciones |
| `/pos` | `pos` | Punto de venta |
| `/inventory` | `inventory` | Control de inventario |
| `/reports` | `reports` | Reportes |
| `/import` | `import` | Importación de datos |
| `/users` | `users` | Gestión de usuarios |
| `/roles` | `permissions` | Roles y permisos |

## ⚠️ Notas Importantes

1. **Los cambios de permisos son inmediatos** - El usuario debe hacer logout y login para ver los nuevos permisos

2. **Lógica OR** - Si un usuario tiene múltiples roles, hereda TODOS los permisos de TODOS sus roles

3. **Permiso READ es obligatorio** - Para ver un módulo en el menú, el usuario necesita al menos permiso READ

4. **Sin permisos = Sin acceso** - Si un usuario intenta acceder a una ruta sin permisos, será redirigido

5. **Roles inactivos** - Los roles desactivados no otorgan permisos, aunque estén asignados al usuario

6. **Usuarios inactivos** - Los usuarios desactivados no pueden hacer login

## 🔍 Solución de Problemas

### Problema: No veo ningún módulo en el menú
**Causa:** Tu usuario no tiene roles asignados o los roles no tienen permisos  
**Solución:** Contacta al administrador para que te asigne roles

### Problema: Veo el módulo pero no los botones de crear/editar
**Causa:** Tienes permiso READ pero no CREATE/UPDATE  
**Solución:** Solicita al administrador que actualice los permisos de tu rol

### Problema: Cambié permisos pero no se reflejan
**Causa:** Los permisos se cargan al hacer login  
**Solución:** Cierra sesión y vuelve a iniciar sesión

### Problema: No puedo acceder a Usuarios o Roles
**Causa:** Solo el rol Administrador tiene acceso por defecto  
**Solución:** Solicita acceso al administrador o que te asigne rol Administrador

## 📞 Próximos Pasos

Para mejorar aún más el sistema, considera:

1. **Auditoría**: Registrar quién cambió qué permisos y cuándo
2. **Permisos temporales**: Asignar permisos con fecha de expiración
3. **Permisos granulares**: Agregar permisos como "approve", "export", "import"
4. **Notificaciones**: Alertar a usuarios cuando sus permisos cambian
5. **Dashboard de permisos**: Vista resumen de todos los permisos del usuario

---

**Versión**: 1.0.0  
**Última actualización**: Enero 2025
