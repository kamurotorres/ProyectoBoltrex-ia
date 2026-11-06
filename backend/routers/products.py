from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from core.dates import now_utc, as_datetime
from core.database import db
from core.permissions import require_permission, require_any_permission
from core.transactions import run_in_transaction
from core import audit
from core.pricing import validate_pricing, validate_price_lists
from core.pagination import page_params, paginate, search_filter, combine
from models.auth import User
from models.inventory import Category, CategoryCreate, PriceList, PriceListCreate, PriceListUpdate, Product, ProductCreate, ProductUpdate

router = APIRouter(tags=["Products"])
# ==================== CATEGORIES ====================

@router.post("/categories", response_model=Category)
async def create_category(category: CategoryCreate, current_user: User = Depends(require_permission("categories", "create"))):
    existing = await db.categories.find_one({"name": category.name})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe una categoría llamada '{category.name}'")

    cat_dict = category.model_dump()
    cat_dict["created_at"] = now_utc()
    await db.categories.insert_one(cat_dict)
    await audit.record("categories", "create", entity_id=category.name, entity_name=category.name,
                       summary=f"Creó la categoría '{category.name}'", after=cat_dict)
    return Category(**cat_dict)

@router.get("/categories")
async def get_categories(paginated: bool = False, search: Optional[str] = None, pg: dict = Depends(page_params),
                         current_user: User = Depends(require_any_permission(("categories", "read"), ("products", "read")))):
    # P1.18: con `paginated=true` (pantalla de administración) responde paginado y con búsqueda en el
    # servidor; sin él, la lista completa para los selectores de otras pantallas (son catálogos pequeños).
    query = search_filter(search, ["name", "description"]) or {}
    if paginated:
        return await paginate(db.categories, query, [("name", 1)], **pg)
    return await db.categories.find(query, {"_id": 0}).sort([("name", 1), ("_id", 1)]).to_list(None)

@router.put("/categories/{name}", response_model=Category)
async def update_category(name: str, category: CategoryCreate, current_user: User = Depends(require_permission("categories", "update"))):
    new_name = (category.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="El nombre de la categoría no puede estar vacío")

    async def _update(session):
        before = await db.categories.find_one({"name": name}, {"_id": 0}, session=session)
        if not before:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        if new_name != name and await db.categories.find_one({"name": new_name}, {"_id": 1}, session=session):
            raise HTTPException(status_code=400, detail=f"Ya existe una categoría llamada '{new_name}'")

        await db.categories.update_one(
            {"name": name}, {"$set": {"name": new_name, "description": category.description}}, session=session
        )
        renamed = 0
        if new_name != name:
            # Los productos guardan el nombre de su categoría: se actualizan en la misma transacción.
            result = await db.products.update_many({"category": name}, {"$set": {"category": new_name}}, session=session)
            renamed = result.modified_count
        after = {**before, "name": new_name, "description": category.description}
        changes = audit.diff(before, after)
        summary = f"Modificó la categoría '{name}': {audit.describe_changes(changes)}"
        if renamed:
            summary += f" ({renamed} producto(s) actualizados)"
        await audit.record("categories", "update", entity_id=new_name, entity_name=new_name, summary=summary,
                           before=before, after=after, details={"products_renamed": renamed}, session=session)
        return renamed

    await run_in_transaction(_update)

    updated = await db.categories.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return Category(**updated)

@router.delete("/categories/{name}")
async def delete_category(name: str, current_user: User = Depends(require_permission("categories", "delete"))):
    if not await db.categories.find_one({"name": name}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    in_use = await db.products.count_documents({"category": name})
    if in_use:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar la categoría '{name}': está asignada a {in_use} producto(s). "
                   f"Cámbiales la categoría antes de eliminarla.",
        )
    before = await db.categories.find_one({"name": name}, {"_id": 0})
    await db.categories.delete_one({"name": name})
    await audit.record("categories", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó la categoría '{name}'", before=before)
    return {"message": "Categoría eliminada"}

# ==================== PRICE LISTS ====================

# Lista que se asigna por defecto a los clientes (modelo Client.price_list): no se renombra ni se borra.
DEFAULT_PRICE_LIST = "default"


@router.post("/price-lists", response_model=PriceList)
async def create_price_list(price_list: PriceListCreate, current_user: User = Depends(require_permission("price-lists", "create"))):
    pl_dict = price_list.model_dump()
    pl_dict["name"] = (pl_dict.get("name") or "").strip()
    if not pl_dict["name"]:
        raise HTTPException(status_code=400, detail="El nombre de la lista de precios no puede estar vacío")
    if await db.price_lists.find_one({"name": pl_dict["name"]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Ya existe una lista de precios llamada '{pl_dict['name']}'")
    pl_dict["created_at"] = now_utc()
    await db.price_lists.insert_one(dict(pl_dict))
    await audit.record("price-lists", "create", entity_id=pl_dict["name"], entity_name=pl_dict["name"],
                       summary=f"Creó la lista de precios '{pl_dict['name']}'", after=pl_dict)
    return PriceList(**pl_dict)

@router.get("/price-lists")
async def get_price_lists(paginated: bool = False, search: Optional[str] = None, pg: dict = Depends(page_params),
                          current_user: User = Depends(require_any_permission(("price-lists", "read"), ("products", "read"), ("clients", "read")))):
    # P1.18: con `paginated=true` (pantalla de administración) responde paginado y con búsqueda en el
    # servidor; sin él, la lista completa para los selectores de otras pantallas (son catálogos pequeños).
    query = search_filter(search, ["name", "description"]) or {}
    if paginated:
        return await paginate(db.price_lists, query, [("name", 1)], **pg)
    return await db.price_lists.find(query, {"_id": 0}).sort([("name", 1), ("_id", 1)]).to_list(None)

@router.put("/price-lists/{name}", response_model=PriceList)
async def update_price_list(name: str, pl_update: PriceListUpdate, current_user: User = Depends(require_permission("price-lists", "update"))):
    update_data = {k: v for k, v in pl_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
        if not update_data["name"]:
            raise HTTPException(status_code=400, detail="El nombre de la lista de precios no puede estar vacío")
    new_name = update_data.get("name", name)

    if name == DEFAULT_PRICE_LIST and new_name != name:
        raise HTTPException(
            status_code=400,
            detail=f"La lista '{DEFAULT_PRICE_LIST}' es la que se asigna por defecto a los clientes y no se puede renombrar.",
        )

    async def _update(session):
        before = await db.price_lists.find_one({"name": name}, {"_id": 0}, session=session)
        if not before:
            raise HTTPException(status_code=404, detail="Lista de precios no encontrada")
        if new_name != name and await db.price_lists.find_one({"name": new_name}, {"_id": 1}, session=session):
            raise HTTPException(status_code=400, detail=f"Ya existe una lista de precios llamada '{new_name}'")

        await db.price_lists.update_one({"name": name}, {"$set": update_data}, session=session)
        if new_name != name:
            # Sin esto, los clientes de la lista dejarían de encontrar su precio y el POS
            # les cobraría el precio de respaldo (costo × 1.3) sin avisar.
            await db.products.update_many(
                {"prices.price_list_name": name},
                {"$set": {"prices.$[p].price_list_name": new_name}},
                array_filters=[{"p.price_list_name": name}],
                session=session,
            )
            await db.clients.update_many({"price_list": name}, {"$set": {"price_list": new_name}}, session=session)
        after = {**before, **update_data}
        await audit.record("price-lists", "update", entity_id=new_name, entity_name=new_name,
                           summary=f"Modificó la lista de precios '{name}': {audit.describe_changes(audit.diff(before, after))}",
                           before=before, after=after, session=session)

    await run_in_transaction(_update)

    updated = await db.price_lists.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return PriceList(**updated)

@router.delete("/price-lists/{name}")
async def delete_price_list(name: str, current_user: User = Depends(require_permission("price-lists", "delete"))):
    if name == DEFAULT_PRICE_LIST:
        raise HTTPException(
            status_code=400,
            detail=f"La lista '{DEFAULT_PRICE_LIST}' es la que se asigna por defecto a los clientes y no se puede eliminar.",
        )
    if not await db.price_lists.find_one({"name": name}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

    clients_using = await db.clients.count_documents({"price_list": name})
    products_using = await db.products.count_documents({"prices.price_list_name": name})
    if clients_using or products_using:
        reasons = []
        if clients_using:
            reasons.append(f"está asignada a {clients_using} cliente(s)")
        if products_using:
            reasons.append(f"tiene precios definidos en {products_using} producto(s)")
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar la lista '{name}': {' y '.join(reasons)}. "
                   f"Asigna otra lista a esos clientes y quita esos precios de los productos antes de eliminarla.",
        )
    before = await db.price_lists.find_one({"name": name}, {"_id": 0})
    await db.price_lists.delete_one({"name": name})
    await audit.record("price-lists", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó la lista de precios '{name}'", before=before)
    return {"message": "Lista de precios eliminada"}

# ==================== PRODUCTS ====================

@router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, current_user: User = Depends(require_permission("products", "create"))):
    existing = await db.products.find_one({"barcode": product.barcode})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un producto con el código de barras '{product.barcode}'")
    # P1.16/P1.17: IVA 0–100, precios obligatorios (con 'default'), > 0 y ≥ precio de compra.
    validate_pricing(product.purchase_price, product.tax_rate, product.prices)
    await validate_price_lists(product.prices)

    prod_dict = product.model_dump()
    if prod_dict.get("min_stock") is None:   # P2.34: sin mínimo propio → usa el general
        prod_dict.pop("min_stock", None)
    prod_dict["stock"] = 0
    prod_dict["created_at"] = now_utc()
    await db.products.insert_one(prod_dict)
    await audit.record("products", "create", entity_id=product.barcode, entity_name=product.name,
                       summary=f"Creó el producto '{product.name}'", after=prod_dict)
    return Product(**prod_dict)

@router.get("/products")
async def get_products(search: Optional[str] = None, barcode: Optional[str] = None, pg: dict = Depends(page_params),
                       current_user: User = Depends(require_any_permission(("products", "read"), ("pos", "read"), ("purchases", "read"), ("inventory", "read")))):
    """Productos paginados (P1.18). `search` busca en código y nombre; `barcode` = código exacto (lector)."""
    query = combine(search_filter(search, ["barcode", "name"]), {"barcode": barcode} if barcode else None)
    return await paginate(db.products, query, [("name", 1)], **pg)

@router.get("/products/{barcode}", response_model=Product)
async def get_product(barcode: str, current_user: User = Depends(require_any_permission(("products", "read"), ("pos", "read"), ("purchases", "read"), ("inventory", "read")))):
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if isinstance(product.get('created_at'), str):
        product['created_at'] = as_datetime(product['created_at'])
    return Product(**product)

@router.put("/products/{barcode}", response_model=Product)
async def update_product(barcode: str, product_update: ProductUpdate, current_user: User = Depends(require_permission("products", "update"))):
    update_data = {k: v for k, v in product_update.model_dump().items() if v is not None}
    # P2.34: enviar min_stock vacío (null) lo quita → el producto usa el stock mínimo general.
    unset_min = "min_stock" in product_update.model_fields_set and product_update.min_stock is None
    if not update_data and not unset_min:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    before = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    # P1.16/P1.17: se valida cómo QUEDA el producto (p. ej. subir el costo por encima de un precio).
    merged = {**before, **update_data}
    validate_pricing(merged.get("purchase_price"), merged.get("tax_rate"), merged.get("prices"))
    # Listas existentes; en una lista inactiva solo se conserva el precio que ya tenía (opción A).
    await validate_price_lists(merged.get("prices"), before.get("prices"))
    ops = {}
    if update_data:
        ops["$set"] = update_data
    if unset_min:
        ops["$unset"] = {"min_stock": ""}
    result = await db.products.update_one({"barcode": barcode}, ops)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    updated = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    changes = audit.diff(before, updated)
    if changes:
        await audit.record("products", "update", entity_id=barcode, entity_name=updated.get("name"),
                           summary=f"Modificó '{updated.get('name')}': {audit.describe_changes(changes)}",
                           before=before, after=updated)
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return Product(**updated)

@router.delete("/products/{barcode}")
async def delete_product(barcode: str, current_user: User = Depends(require_permission("products", "delete"))):
    before = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    result = await db.products.delete_one({"barcode": barcode})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    await audit.record("products", "delete", entity_id=barcode, entity_name=(before or {}).get("name"),
                       summary=f"Eliminó el producto '{(before or {}).get('name', barcode)}' (stock {(before or {}).get('stock', 0)})",
                       before=before)
    return {"message": "Producto eliminado"}

