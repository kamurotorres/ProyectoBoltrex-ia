# Módulo de Importación - Boltrex

## 📥 Descripción

El módulo de importación permite cargar datos masivamente desde archivos CSV o Excel (.xlsx, .xls) para poblar rápidamente las siguientes entidades:

- **Categorías**
- **Productos**
- **Clientes**
- **Proveedores**

## 🚀 Características

- ✅ Soporte para archivos CSV y Excel (.xlsx, .xls)
- ✅ Descarga de plantillas con ejemplos
- ✅ Validación de datos antes de importar
- ✅ Reporte detallado de éxitos y errores
- ✅ Prevención de duplicados
- ✅ Interfaz intuitiva con tabs por módulo

## 📊 Módulos de Importación

### 1. Categorías

**Columnas Requeridas:**
- `name` - Nombre de la categoría (único)
- `description` - Descripción de la categoría

**Ejemplo CSV:**
```csv
name,description
Electrónica,Dispositivos electrónicos y accesorios
Alimentos,Productos alimenticios
Bebidas,Bebidas y refrescos
```

### 2. Productos

**Columnas Requeridas:**
- `barcode` - Código de barras (único)
- `name` - Nombre del producto
- `category` - Nombre de la categoría (debe existir previamente)
- `purchase_price` - Precio de compra
- `tax_rate` - Porcentaje de IVA

**Columnas Opcionales:**
- `description` - Descripción del producto
- `price_default` - Precio para lista "default"
- `price_mayorista` - Precio para lista "mayorista"
- `price_minorista` - Precio para lista "minorista"

**Ejemplo CSV:**
```csv
barcode,name,description,category,purchase_price,tax_rate,price_default,price_mayorista,price_minorista
001,Laptop HP,Laptop HP 15 pulgadas,Electrónica,800,19,1200,1100,1250
002,Mouse Inalámbrico,Mouse óptico inalámbrico,Electrónica,15,19,25,22,28
003,Arroz Premium,Arroz premium 1kg,Alimentos,2.5,5,4.0,3.5,4.5
```

**Nota:** La categoría debe existir antes de importar productos. Importa categorías primero.

### 3. Clientes

**Columnas Requeridas:**
- `document_type` - Tipo de documento (CC, NIT, CE, PAS - debe existir)
- `document_number` - Número de documento (único por tipo)
- `first_name` - Nombres
- `last_name` - Apellidos

**Columnas Opcionales:**
- `phone` - Teléfono
- `email` - Email
- `address` - Dirección
- `latitude` - Latitud para geolocalización
- `longitude` - Longitud para geolocalización
- `price_list` - Lista de precios asignada (default, mayorista, minorista)

**Ejemplo CSV:**
```csv
document_type,document_number,first_name,last_name,phone,email,address,latitude,longitude,price_list
CC,123456789,Juan,Pérez,3001234567,juan@example.com,Calle 123,4.6097,-74.0817,default
NIT,987654321,Empresa,SAS,3009876543,info@empresa.com,Carrera 45,4.6107,-74.0827,mayorista
CE,555555555,María,García,3005555555,maria@test.com,Avenida 10,,,,default
```

**Nota:** El tipo de documento debe existir previamente en el sistema.

### 4. Proveedores

**Columnas Requeridas:**
- `name` - Nombre del proveedor

**Columnas Opcionales:**
- `contact_name` - Nombre del contacto
- `phone` - Teléfono
- `email` - Email
- `address` - Dirección

**Ejemplo CSV:**
```csv
name,contact_name,phone,email,address
Proveedor ABC,María López,3001111111,maria@abc.com,Avenida 1
Distribuidora XYZ,Carlos García,3002222222,carlos@xyz.com,Calle 2
Importadora 123,Ana Martínez,3003333333,ana@123.com,Carrera 3
```

## 🔄 Proceso de Importación

### Paso 1: Preparar los Datos

1. Descarga la plantilla correspondiente desde el módulo de importación
2. Abre el archivo con Excel, Google Sheets o cualquier editor de hojas de cálculo
3. Completa tus datos siguiendo el formato de la plantilla
4. Guarda el archivo en formato CSV o Excel

### Paso 2: Validar Datos

Antes de importar, verifica que:

- ✅ Todas las columnas requeridas estén completas
- ✅ No haya códigos/documentos duplicados
- ✅ Las referencias (categorías, tipos de documento) existan en el sistema
- ✅ Los datos numéricos estén en el formato correcto (usa punto para decimales)
- ✅ Los emails tengan formato válido

### Paso 3: Importar

1. Ve al módulo **Importar** en el menú lateral
2. Selecciona el tab correspondiente al tipo de dato
3. Haz clic en **"Seleccionar y Cargar Archivo"**
4. Elige tu archivo CSV o Excel
5. Espera a que se procese

### Paso 4: Revisar Resultados

El sistema mostrará:
- ✅ **Exitosos**: Número de registros importados correctamente
- ❌ **Con Errores**: Registros que no pudieron importarse
- 📊 **Total**: Total de registros en el archivo

Si hay errores, se mostrará una tabla detallada con:
- Número de fila del error
- Descripción del problema

## ⚠️ Errores Comunes

### Error: "Ya existe"
**Causa:** El código/documento ya está registrado en el sistema  
**Solución:** Verifica que no haya duplicados en tu archivo o en la base de datos

### Error: "Categoría no existe"
**Causa:** Intentas importar un producto con una categoría que no existe  
**Solución:** Importa primero las categorías, luego los productos

### Error: "Tipo de documento no existe"
**Causa:** El tipo de documento del cliente no está registrado  
**Solución:** Verifica que uses CC, NIT, CE o PAS (códigos existentes)

### Error: "Columnas requeridas"
**Causa:** Falta alguna columna obligatoria en el archivo  
**Solución:** Descarga la plantilla nuevamente y asegúrate de incluir todas las columnas

### Error al leer archivo
**Causa:** El archivo está corrupto o en formato no soportado  
**Solución:** Guarda nuevamente en formato CSV o Excel (.xlsx, .xls)

## 💡 Mejores Prácticas

### 1. Orden de Importación Recomendado

Para evitar errores de referencias, importa en este orden:

1. **Categorías** (primero)
2. **Productos** (requiere categorías)
3. **Clientes** (independiente)
4. **Proveedores** (independiente)

### 2. Preparación de Datos

- Usa Excel o Google Sheets para preparar tus datos
- Verifica que no haya espacios extra al inicio o final de los valores
- Usa punto (.) como separador decimal: `100.50` no `100,50`
- Para campos vacíos opcionales, simplemente déjalos en blanco

### 3. Archivos Grandes

- Si tienes muchos registros (>1000), considera dividir en archivos más pequeños
- Esto facilitará identificar errores específicos
- El sistema puede procesar archivos grandes, pero archivos pequeños son más manejables

### 4. Prueba Primero

- Antes de importar toda tu base de datos, prueba con 5-10 registros
- Verifica que todo se importe correctamente
- Luego procede con el resto de datos

### 5. Backup

- Antes de hacer importaciones masivas, considera hacer un backup
- Esto te permitirá revertir cambios si algo sale mal

## 🔧 Especificaciones Técnicas

### Formatos Soportados
- CSV (UTF-8 con BOM recomendado)
- Excel 2007+ (.xlsx)
- Excel 97-2003 (.xls)

### Límites
- Tamaño máximo de archivo: Según configuración del servidor
- No hay límite en número de registros por archivo
- Recomendado: Máximo 5000 registros por importación

### Validaciones Automáticas

El sistema valida automáticamente:
- ✅ Tipos de datos (números, emails, etc.)
- ✅ Campos requeridos
- ✅ Unicidad de códigos/documentos
- ✅ Existencia de referencias (categorías, tipos de documento)
- ✅ Formato de emails
- ✅ Rangos numéricos válidos

## 📝 Ejemplos Completos

### Ejemplo 1: Importar Catálogo Completo

**Paso 1: Categorías (categorias.csv)**
```csv
name,description
Electrónica,Dispositivos y accesorios electrónicos
Hogar,Artículos para el hogar
Oficina,Suministros de oficina
```

**Paso 2: Productos (productos.csv)**
```csv
barcode,name,description,category,purchase_price,tax_rate,price_default,price_mayorista
001,Laptop Dell,Laptop Dell Inspiron 15,Electrónica,700,19,1100,1000
002,Mouse USB,Mouse óptico USB,Electrónica,8,19,15,13
003,Licuadora,Licuadora 5 velocidades,Hogar,45,19,75,68
004,Resma Papel,Resma papel carta 500 hojas,Oficina,12,19,20,18
```

### Ejemplo 2: Importar Base de Clientes

**clientes.csv**
```csv
document_type,document_number,first_name,last_name,phone,email,price_list
CC,10111111,Pedro,Gómez,3011111111,pedro@mail.com,default
CC,20222222,Laura,Silva,3022222222,laura@mail.com,minorista
NIT,30333333,Tienda,Express,3033333333,tienda@mail.com,mayorista
CC,40444444,Miguel,Torres,3044444444,miguel@mail.com,default
```

## 🆘 Soporte

Si encuentras problemas durante la importación:

1. Verifica la tabla de errores detallada
2. Corrige los registros problemáticos
3. Vuelve a intentar la importación
4. Los registros exitosos no se duplicarán (se detecta automáticamente)

## 🔐 Seguridad

- ✅ Todas las importaciones requieren autenticación
- ✅ Se registra quién realizó la importación (auditoría)
- ✅ Los archivos no se almacenan en el servidor (solo se procesan)
- ✅ Validación de permisos por rol de usuario

---

**Versión**: 1.0.0  
**Última actualización**: Enero 2025
