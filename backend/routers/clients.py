from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from core.dates import now_utc, as_datetime
from core.database import db
from core.permissions import require_permission, require_any_permission
from core.transactions import run_in_transaction
from core import audit
from repositories.clients import resolve_client, invoices_of_client_query, client_label
from core.user_protection import actor_is_admin

CREDIT_ONLY_ADMIN = ("Solo un administrador puede asignar o cambiar el plazo y el cupo de crédito de un cliente "
                     "(son el control de cuánto se le fía). Deja esos campos vacíos o pídeselo a un administrador.")
from core.pagination import page_params, paginate, search_filter
from models.auth import User
from models.entities import Client, ClientCreate, ClientUpdate, DocumentType, DocumentTypeCreate, Supplier, SupplierCreate, SupplierUpdate

router = APIRouter(tags=["Clients"])
# ==================== DOCUMENT TYPES ====================

@router.post("/document-types", response_model=DocumentType)
async def create_document_type(doc_type: DocumentTypeCreate, current_user: User = Depends(require_permission("clients", "create"))):
    existing = await db.document_types.find_one({"code": doc_type.code})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un tipo de documento con el código '{doc_type.code}'")

    dt_dict = doc_type.model_dump()
    dt_dict["created_at"] = now_utc()
    await db.document_types.insert_one(dt_dict)
    await audit.record("document-types", "create", entity_id=doc_type.code, entity_name=dt_dict.get("name"),
                       summary=f"Creó el tipo de documento '{doc_type.code}'", after=dt_dict)
    return DocumentType(**dt_dict)

@router.get("/document-types", response_model=List[DocumentType])
async def get_document_types(current_user: User = Depends(require_any_permission(("clients", "read"), ("import", "read")))):
    doc_types = await db.document_types.find({}, {"_id": 0}).to_list(None)
    for dt in doc_types:
        if isinstance(dt.get('created_at'), str):
            dt['created_at'] = as_datetime(dt['created_at'])
    return doc_types

# ==================== CLIENTS ====================

@router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(require_permission("clients", "create"))):
    existing = await db.clients.find_one({
        "document_type": client.document_type,
        "document_number": client.document_number
    })
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un cliente con el documento {client.document_type} {client.document_number}")

    if (client.credit_days is not None or client.credit_limit) and not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail=CREDIT_ONLY_ADMIN)
    client_dict = client.model_dump()
    for k in ("credit_days", "credit_limit"):   # P2.30: vacío = plazo por defecto / sin cupo
        if client_dict.get(k) in (None, 0) and not (k == "credit_days" and client_dict.get(k) == 0):
            client_dict.pop(k, None)
    client_dict["created_at"] = now_utc()
    await db.clients.insert_one(client_dict)
    full = f"{client.first_name} {client.last_name}".strip()
    await audit.record("clients", "create", entity_id=f"{client.document_type} {client.document_number}", entity_name=full,
                       summary=f"Creó el cliente '{full}'", after=client_dict)
    return Client(**client_dict)

@router.get("/clients")
async def get_clients(search: Optional[str] = None, pg: dict = Depends(page_params),
                      current_user: User = Depends(require_any_permission(("clients", "read"), ("pos", "read"), ("fios", "read")))):
    """Clientes paginados (P1.18). `search` busca en documento, nombre, apellido y email."""
    query = search_filter(search, ["document_number", "first_name", "last_name", "email"]) or {}
    return await paginate(db.clients, query, [("first_name", 1), ("last_name", 1)], **pg)

@router.get("/clients/{document_number}", response_model=Client)
async def get_client(document_number: str, document_type: Optional[str] = None,
                     current_user: User = Depends(require_any_permission(("clients", "read"), ("pos", "read"), ("fios", "read")))):
    client = await resolve_client(document_number, document_type)
    if isinstance(client.get('created_at'), str):
        client['created_at'] = as_datetime(client['created_at'])
    return Client(**client)

@router.put("/clients/{document_number}", response_model=Client)
async def update_client(document_number: str, client_update: ClientUpdate, document_type: Optional[str] = None,
                        current_user: User = Depends(require_permission("clients", "update"))):
    update_data = {k: v for k, v in client_update.model_dump().items() if v is not None}
    # P2.30: enviar plazo/cupo vacío (null) los quita: el cliente vuelve al plazo por defecto / sin cupo.
    to_unset = {k: "" for k in ("credit_days", "credit_limit")
                if k in client_update.model_fields_set and getattr(client_update, k) is None}
    if update_data.get("credit_limit") == 0:
        update_data.pop("credit_limit")
        to_unset["credit_limit"] = ""
    if not update_data and not to_unset:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    before = await resolve_client(document_number, document_type)
    key = {"document_type": before["document_type"], "document_number": document_number}
    credit_changes = {k for k in ("credit_days", "credit_limit")
                      if (k in update_data and update_data[k] != before.get(k)) or (k in to_unset and before.get(k) is not None)}
    if credit_changes and not await actor_is_admin(current_user.email):
        raise HTTPException(status_code=403, detail=CREDIT_ONLY_ADMIN)
    ops = {}
    if update_data:
        ops["$set"] = update_data
    if to_unset:
        ops["$unset"] = to_unset
    result = await db.clients.update_one(key, ops)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    updated = await db.clients.find_one(key, {"_id": 0})
    changes = audit.diff(before, updated)
    if changes:
        full = f"{updated.get('first_name', '')} {updated.get('last_name', '')}".strip()
        await audit.record("clients", "update", entity_id=client_label(updated.get("document_type"), document_number),
                           entity_name=full, summary=f"Modificó el cliente '{full}': {audit.describe_changes(changes)}",
                           before=before, after=updated)
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return Client(**updated)

@router.delete("/clients/{document_number}")
async def delete_client(document_number: str, document_type: Optional[str] = None,
                        current_user: User = Depends(require_permission("clients", "delete"))):
    before = await resolve_client(document_number, document_type)
    label = client_label(before.get("document_type"), document_number)
    full = f"{before.get('first_name', '')} {before.get('last_name', '')}".strip()

    # P1.15: no se borra un cliente con facturas (quedarían sin cliente y su crédito huérfano).
    inv_query = invoices_of_client_query(before)
    invoices_count = await db.invoices.count_documents(inv_query)
    if invoices_count:
        pending = await db.invoices.aggregate([
            {"$match": {**inv_query, "payment_status": "por_cobrar", "balance": {"$gt": 0}}},
            {"$group": {"_id": None, "balance": {"$sum": "$balance"}, "n": {"$sum": 1}}},
        ]).to_list(1)
        reason = f"tiene {invoices_count} factura(s)"
        if pending:
            reason += f" y un saldo pendiente en Fios de ${pending[0]['balance']:,.0f}".replace(",", ".")
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar el cliente '{full}' ({label}): {reason}. "
                   f"Los clientes con historial de ventas se conservan para no perder ese historial.",
        )

    result = await db.clients.delete_one({"document_type": before["document_type"], "document_number": document_number})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await audit.record("clients", "delete", entity_id=label, entity_name=full,
                       summary=f"Eliminó el cliente '{full}'", before=before)
    return {"message": "Cliente eliminado"}

# ==================== SUPPLIERS ====================

@router.post("/suppliers", response_model=Supplier)
async def create_supplier(supplier: SupplierCreate, current_user: User = Depends(require_permission("suppliers", "create"))):
    supp_dict = supplier.model_dump()
    supp_dict["name"] = (supp_dict.get("name") or "").strip()
    if not supp_dict["name"]:
        raise HTTPException(status_code=400, detail="El nombre del proveedor no puede estar vacío")
    if await db.suppliers.find_one({"name": supp_dict["name"]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Ya existe un proveedor llamado '{supp_dict['name']}'")
    supp_dict["created_at"] = now_utc()
    await db.suppliers.insert_one(dict(supp_dict))
    await audit.record("suppliers", "create", entity_id=supp_dict["name"], entity_name=supp_dict["name"],
                       summary=f"Creó el proveedor '{supp_dict['name']}'", after=supp_dict)
    return Supplier(**supp_dict)

@router.get("/suppliers")
async def get_suppliers(search: Optional[str] = None, pg: dict = Depends(page_params),
                        current_user: User = Depends(require_any_permission(("suppliers", "read"), ("purchases", "read")))):
    """Proveedores paginados (P1.18)."""
    query = search_filter(search, ["name", "nit", "contact_name", "phone", "email"]) or {}
    return await paginate(db.suppliers, query, [("name", 1)], **pg)

@router.put("/suppliers/{supplier_name}", response_model=Supplier)
async def update_supplier(supplier_name: str, supplier_update: SupplierUpdate, current_user: User = Depends(require_permission("suppliers", "update"))):
    update_data = {k: v for k, v in supplier_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
        if not update_data["name"]:
            raise HTTPException(status_code=400, detail="El nombre del proveedor no puede estar vacío")
    new_name = update_data.get("name", supplier_name)

    async def _update(session):
        before = await db.suppliers.find_one({"name": supplier_name}, {"_id": 0}, session=session)
        if not before:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        if new_name != supplier_name and await db.suppliers.find_one({"name": new_name}, {"_id": 1}, session=session):
            raise HTTPException(status_code=400, detail=f"Ya existe un proveedor llamado '{new_name}'")

        await db.suppliers.update_one({"name": supplier_name}, {"$set": update_data}, session=session)
        after = {**before, **update_data}
        await audit.record("suppliers", "update", entity_id=new_name, entity_name=new_name,
                           summary=f"Modificó el proveedor '{supplier_name}': {audit.describe_changes(audit.diff(before, after))}",
                           before=before, after=after, session=session)
        if new_name != supplier_name:
            # Solo las compras en borrador siguen el nombre nuevo; las confirmadas conservan
            # el nombre con el que se registraron (registro histórico).
            await db.purchases.update_many(
                {"supplier_name": supplier_name, "status": "borrador"},
                {"$set": {"supplier_name": new_name}},
                session=session,
            )

    await run_in_transaction(_update)

    updated = await db.suppliers.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return Supplier(**updated)

@router.delete("/suppliers/{supplier_name}")
async def delete_supplier(supplier_name: str, current_user: User = Depends(require_permission("suppliers", "delete"))):
    if not await db.suppliers.find_one({"name": supplier_name}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    drafts = await db.purchases.count_documents({"supplier_name": supplier_name, "status": "borrador"})
    if drafts:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar el proveedor '{supplier_name}': tiene {drafts} compra(s) en borrador. "
                   f"Confírmalas o cámbialas de proveedor antes de eliminarlo.",
        )
    before = await db.suppliers.find_one({"name": supplier_name}, {"_id": 0})
    await db.suppliers.delete_one({"name": supplier_name})
    await audit.record("suppliers", "delete", entity_id=supplier_name, entity_name=supplier_name,
                       summary=f"Eliminó el proveedor '{supplier_name}'", before=before)
    return {"message": "Proveedor eliminado"}
