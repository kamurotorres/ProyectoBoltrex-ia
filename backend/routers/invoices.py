import re
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import timedelta
from typing import List, Optional, Dict, Any
from core.dates import now_utc, as_datetime
from core.database import db
from core.database import get_db
from core.security import get_current_user
from core.permissions import require_permission, require_any_permission
from core.transactions import run_in_transaction
from core.counters import INVOICE_COUNTER, ensure_counter, next_number
import uuid
from models.auth import User
from models.billing import FioPaymentCreate, Invoice, InvoiceCreate, PaymentMethod, PaymentMethodCreate, PaymentMethodUpdate, Return, ReturnCreate, TaxRate, TaxRateCreate
import io
import csv
from fastapi.responses import StreamingResponse
from ticket_generator import TicketPDFGenerator

from core import audit
from core.sales import created_at_range
from core.clients import resolve_client, invoices_of_client_query
from core.pricing import unit_price_for
from core.cash import CASH_METHOD, add_movement, session_for_money
from core import credit
from core.pagination import page_params, paginate, paginate_pipeline, search_filter, combine

router = APIRouter(tags=["Billing"])
db_dep = Depends(get_db)
# ==================== TAX RATES ====================

@router.post("/tax-rates", response_model=TaxRate)
async def create_tax_rate(tax_rate: TaxRateCreate, current_user: User = Depends(require_permission("permissions", "update"))):
    if tax_rate.is_active:
        await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})

    tr_dict = tax_rate.model_dump()
    if tr_dict.get("effective_date"):
        tr_dict["effective_date"] = as_datetime(tr_dict["effective_date"])
    else:
        tr_dict["effective_date"] = now_utc()
    tr_dict["created_at"] = now_utc()

    await db.tax_rates.insert_one(tr_dict)
    await audit.record("tax-rates", "create", entity_id=tr_dict.get("name"), entity_name=tr_dict.get("name"),
                       summary=f"Creó la tarifa de IVA '{tr_dict.get('name')}' ({tr_dict.get('rate')})"
                               + (" y la dejó activa" if tax_rate.is_active else ""), after=tr_dict)
    return TaxRate(**{**tr_dict, "effective_date": as_datetime(tr_dict["effective_date"]), "created_at": as_datetime(tr_dict["created_at"])})

@router.get("/tax-rates", response_model=List[TaxRate])
async def get_tax_rates(current_user: User = Depends(get_current_user)):
    tax_rates = await db.tax_rates.find({}, {"_id": 0}).to_list(None)
    for tr in tax_rates:
        if isinstance(tr.get('effective_date'), str):
            tr['effective_date'] = as_datetime(tr['effective_date'])
        if isinstance(tr.get('created_at'), str):
            tr['created_at'] = as_datetime(tr['created_at'])
    return tax_rates

@router.patch("/tax-rates/{name}/activate")
async def activate_tax_rate(name: str, current_user: User = Depends(require_permission("permissions", "update"))):
    if not await db.tax_rates.find_one({"name": name}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Tarifa de IVA no encontrada")
    previous = await db.tax_rates.find_one({"is_active": True}, {"_id": 0, "name": 1})
    await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    result = await db.tax_rates.update_one({"name": name}, {"$set": {"is_active": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tarifa de IVA no encontrada")
    prev_name = (previous or {}).get("name")
    await audit.record("tax-rates", "activate", entity_id=name, entity_name=name,
                       summary=f"Activó la tarifa de IVA '{name}'" + (f" (antes: '{prev_name}')" if prev_name else ""),
                       before={"tarifa_activa": prev_name}, after={"tarifa_activa": name})
    return {"message": "Tax rate activated"}

# ==================== PAYMENT METHODS ====================

@router.post("/payment-methods", response_model=PaymentMethod)
async def create_payment_method(payment_method: PaymentMethodCreate, current_user: User = Depends(require_permission("payment-methods", "create"))):
    """Crear una nueva forma de pago"""
    existing = await db.payment_methods.find_one({"name": payment_method.name})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")

    pm_dict = payment_method.model_dump()
    pm_dict["created_at"] = now_utc()
    await db.payment_methods.insert_one(pm_dict)
    await audit.record("payment-methods", "create", entity_id=payment_method.name, entity_name=payment_method.name,
                       summary=f"Creó la forma de pago '{payment_method.name}'", after=pm_dict)
    return PaymentMethod(**pm_dict)

@router.get("/payment-methods")
async def get_payment_methods(paginated: bool = False, search: Optional[str] = None, pg: dict = Depends(page_params),
                              current_user: User = Depends(require_permission("payment-methods", "read"))):
    """Listar formas de pago"""
    # P1.18: con `paginated=true` (pantalla de administración) responde paginado y con búsqueda en el
    # servidor; sin él, la lista completa para los selectores de otras pantallas (son catálogos pequeños).
    query = search_filter(search, ["name", "description"]) or {}
    if paginated:
        return await paginate(db.payment_methods, query, [("name", 1)], **pg)
    return await db.payment_methods.find(query, {"_id": 0}).sort([("name", 1), ("_id", 1)]).to_list(None)

@router.get("/payment-methods/active", response_model=List[PaymentMethod])
async def get_active_payment_methods(current_user: User = Depends(require_any_permission(("payment-methods", "read"), ("pos", "read"), ("fios", "read")))):
    """Listar solo formas de pago activas (para POS y Fios)"""
    payment_methods = await db.payment_methods.find({"is_active": True}, {"_id": 0}).to_list(None)
    for pm in payment_methods:
        if isinstance(pm.get('created_at'), str):
            pm['created_at'] = as_datetime(pm['created_at'])
    return payment_methods

@router.put("/payment-methods/{name}", response_model=PaymentMethod)
async def update_payment_method(name: str, payment_method: PaymentMethodUpdate, current_user: User = Depends(require_permission("payment-methods", "update"))):
    """Actualizar una forma de pago"""
    update_data = {k: v for k, v in payment_method.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Check if new name already exists (if changing name)
    if "name" in update_data and update_data["name"] != name:
        existing = await db.payment_methods.find_one({"name": update_data["name"]})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")

    before = await db.payment_methods.find_one({"name": name}, {"_id": 0})
    result = await db.payment_methods.update_one({"name": name}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    after = {**before, **update_data}
    await audit.record("payment-methods", "update", entity_id=update_data.get("name", name), entity_name=update_data.get("name", name),
                       summary=f"Modificó la forma de pago '{name}': {audit.describe_changes(audit.diff(before, after))}",
                       before=before, after=after)

    # Get updated (use new name if changed)
    new_name = update_data.get("name", name)
    updated = await db.payment_methods.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = as_datetime(updated['created_at'])
    return PaymentMethod(**updated)

@router.delete("/payment-methods/{name}")
async def delete_payment_method(name: str, current_user: User = Depends(require_permission("payment-methods", "delete"))):
    """Eliminar una forma de pago"""
    # Check if payment method is being used in any invoice
    usage = await db.invoices.find_one({"payment_method": name})
    if usage:
        raise HTTPException(status_code=400, detail="No se puede eliminar: esta forma de pago está siendo utilizada en facturas")

    before = await db.payment_methods.find_one({"name": name}, {"_id": 0})
    result = await db.payment_methods.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    await audit.record("payment-methods", "delete", entity_id=name, entity_name=name,
                       summary=f"Eliminó la forma de pago '{name}'", before=before)
    return {"message": "Forma de pago eliminada"}

# ==================== INVOICES (POS) ====================

@router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice_data: InvoiceCreate, current_user: User = Depends(require_permission("pos", "create"))):
    # Validate payment_status
    if invoice_data.payment_status not in ["pagado", "por_cobrar"]:
        raise HTTPException(status_code=400, detail="Estado de pago inválido. Use 'pagado' o 'por_cobrar'")

    # If payment_status is "pagado", payment_method is required
    if invoice_data.payment_status == "pagado" and not invoice_data.payment_method:
        raise HTTPException(status_code=400, detail="La forma de pago es obligatoria cuando el estado es 'pagado'")

    if not invoice_data.items:
        raise HTTPException(status_code=400, detail="La factura debe tener al menos un producto")
    # Una cantidad cero o negativa no es una venta (y con -N el descuento de stock lo SUMARÍA).
    for req_item in invoice_data.items:
        if req_item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Cantidad inválida para el producto {req_item.barcode}: debe ser mayor a 0")

    # El documento del contador debe existir ANTES de la transacción (se inicializa a partir de
    # la última factura la primera vez); dentro de la transacción solo se incrementa.
    await ensure_counter(INVOICE_COUNTER)
    credit_settings = await credit.get_settings()
    offset = invoice_data.tz_offset_minutes
    # P2.30: una fecha de vencimiento elegida en el POS se valida antes de tocar nada.
    chosen_due = None
    if invoice_data.payment_status == "por_cobrar" and (invoice_data.due_date or "").strip():
        chosen_due = credit.parse_due_date(invoice_data.due_date, offset)

    async def _create(session):
        if invoice_data.payment_status == "pagado":
            # Verify payment method exists and is active
            payment_method = await db.payment_methods.find_one(
                {"name": invoice_data.payment_method, "is_active": True}, session=session
            )
            if not payment_method:
                raise HTTPException(status_code=400, detail="La forma de pago seleccionada no existe o no está activa")

        # Cliente por tipo + número (P1.15): nunca se toma "cualquiera" de dos con el mismo número.
        client = await resolve_client(invoice_data.client_document, invoice_data.client_document_type, session=session)

        client_name = f"{client['first_name']} {client['last_name']}"
        client_price_list = client.get("price_list", "default")

        processed_items = []
        subtotal = 0.0
        total_tax = 0.0
        total = 0.0

        # Calculate totals securely on the server
        for req_item in invoice_data.items:
            product = await db.products.find_one({"barcode": req_item.barcode}, session=session)
            if not product:
                raise HTTPException(status_code=400, detail=f"Producto con código {req_item.barcode} no encontrado")

            # Chequeo temprano para dar un error claro; la garantía real es el descuento
            # condicionado más abajo (el stock puede cambiar entre esta lectura y la escritura).
            if req_item.quantity > product.get("stock", 0):
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product['name']}")

            # P1.17: precio de la lista del cliente; si el producto no la tiene, el de 'default'.
            # (Antes se inventaba costo × 1,3 sin avisar.)
            unit_price = unit_price_for(product, client_price_list)

            item_subtotal = unit_price * req_item.quantity
            # P1.16: el IVA es el de cada producto.
            item_tax_amount = (item_subtotal * float(product.get("tax_rate") or 0)) / 100
            item_total = item_subtotal + item_tax_amount

            subtotal += item_subtotal
            total_tax += item_tax_amount
            total += item_total

            processed_items.append({
                "barcode": product["barcode"],
                "product_name": product["name"],
                "quantity": req_item.quantity,
                "unit_price": unit_price,
                "tax_rate": float(product.get("tax_rate") or 0),
                # P2.29: precio de compra al momento de la venta → ganancia = (precio venta − compra) × cantidad.
                "unit_cost": float(product.get("purchase_price") or 0),
                "subtotal": item_subtotal,
                "tax_amount": item_tax_amount,
                "total": item_total
            })

        # P2.30: venta a crédito → cupo del cliente (si tiene) y vencimiento.
        due_date, term_days = None, None
        if invoice_data.payment_status == "por_cobrar":
            await credit.check_credit_limit(client, total, session=session)
            if chosen_due is not None:
                due_date = chosen_due
                term_days = ((chosen_due - timedelta(minutes=offset)).date() - credit.local_today(offset)).days
            else:
                term_days = credit.term_for_client(client, credit_settings)
                due_date = credit.due_date_from(now_utc(), term_days, offset)

        # P2.31: caja del vendedor (si el interruptor la exige y no hay, se rechaza con el motivo).
        cash_session_id = await session_for_money(current_user.email, "sale", session=session)

        # Consecutivo: si la transacción se aborta, el incremento también se revierte (sin huecos).
        invoice_number = await next_number(INVOICE_COUNTER, session=session)

        # Determine amount_paid and balance based on payment_status
        if invoice_data.payment_status == "pagado":
            amount_paid = total
            balance = 0
        else:  # por_cobrar
            amount_paid = 0
            balance = total

        now = now_utc()
        invoice_dict = {
            "invoice_number": invoice_number,
            "client_document": invoice_data.client_document,
            "client_document_type": client.get("document_type"),
            "client_name": client_name,
            "items": processed_items,
            "subtotal": subtotal,
            "total_tax": total_tax,
            "total": total,
            "created_by": current_user.email,
            "created_at": now,
            "status": "completed",
            "payment_status": invoice_data.payment_status,
            "payment_method": invoice_data.payment_method if invoice_data.payment_status == "pagado" else None,
            "amount_paid": amount_paid,
            "balance": balance,
            "cash_session_id": cash_session_id,
        }
        if due_date is not None:
            invoice_dict["due_date"] = due_date
            invoice_dict["credit_term_days"] = term_days

        await db.invoices.insert_one(dict(invoice_dict), session=session)
        if invoice_data.payment_status == "pagado" and total > 0:
            await add_movement(cash_session_id, "sale", "in", invoice_dict["payment_method"], total,
                               current_user.email, reference=invoice_number, session=session)

        # Update inventory and create movements
        for item in processed_items:
            # Descuento atómico: solo se aplica si queda stock suficiente EN ESE INSTANTE.
            # Con ventas concurrentes (o la misma referencia repetida en la factura) el stock
            # nunca baja de 0; si no alcanza, la excepción aborta toda la transacción.
            result = await db.products.update_one(
                {"barcode": item["barcode"], "stock": {"$gte": item["quantity"]}},
                {"$inc": {"stock": -item["quantity"]}},
                session=session,
            )
            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {item['product_name']}")
            await db.inventory_movements.insert_one({
                "barcode": item["barcode"],
                "product_name": item["product_name"],
                "movement_type": "sale",
                "quantity": -item["quantity"],
                "reference": invoice_number,
                "created_by": current_user.email,
                "created_at": now
            }, session=session)

        # Bitácora en la misma transacción: si la venta se revierte, el registro también.
        pago = ("de contado (" + str(invoice_dict.get("payment_method")) + ")") if invoice_data.payment_status == "pagado" \
            else f"a crédito (vence {(due_date - timedelta(minutes=offset)).strftime('%d/%m/%Y')})"
        await audit.record("invoices", "create", entity_id=invoice_number, entity_name=client_name,
                           summary=f"Venta {invoice_number} a '{client_name}' por {total:,.0f} {pago}, "
                                   f"{sum(i['quantity'] for i in processed_items)} unidad(es)",
                           after=invoice_dict, session=session)

        return invoice_dict

    invoice_dict = await run_in_transaction(_create)
    # P2.34: aviso en el POS de lo que quedó en bajo stock o agotado con esta venta.
    from core.alerts import stock_warnings
    warnings = await stock_warnings([i["barcode"] for i in invoice_dict["items"]])
    return Invoice(**{**invoice_dict, "created_at": as_datetime(invoice_dict["created_at"]), "stock_warnings": warnings})


@router.get("/invoices")
async def get_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset_minutes: int = 0,
    search: Optional[str] = None,
    exclude_status: Optional[str] = None,
    pg: dict = Depends(page_params),
    current_user: User = Depends(require_any_permission(("invoices", "read"), ("returns", "read")))
):
    """Facturas paginadas, más recientes primero (P1.18). `search`: número, cliente o documento."""
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    query = combine(
        {"created_at": rng} if rng else None,
        {"status": {"$ne": exclude_status}} if exclude_status else None,
        search_filter(search, ["invoice_number", "client_name", "client_document"]),
    )
    return await paginate(db.invoices, query, [("created_at", -1)], **pg)

@router.get("/invoices/{invoice_number}")
async def get_invoice(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("returns", "read")))):
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if isinstance(invoice.get('created_at'), str):
        invoice['created_at'] = invoice['created_at']

    # Get payment history (abonos)
    payments = await db.fio_payments.find(
        {"invoice_number": invoice_number},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Get returns history (devoluciones)
    returns = await db.returns.find(
        {"invoice_number": invoice_number},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return {
        **invoice,
        "payments_history": payments,
        "returns_history": returns
    }

# ==================== RETURNS ====================

# Tolerancia para comparar importes en coma flotante.
_MONEY_EPS = 0.005


@router.post("/returns", response_model=Return)
async def create_return(return_data: ReturnCreate, current_user: User = Depends(require_permission("returns", "create"))):
    """Registrar una devolución validada contra la factura original.

    - Cada producto debe estar en la factura y la cantidad debe ser > 0 y no superar
      lo vendido menos lo ya devuelto en devoluciones anteriores.
    - Precio unitario e IVA se toman de la factura; el importe lo calcula el servidor.
    - Se recalculan subtotal, IVA y total de la factura (y el saldo si es a crédito).
    """
    if not return_data.items:
        raise HTTPException(status_code=400, detail="Selecciona al menos un producto para devolver")

    # Cantidades pedidas por producto (una referencia puede venir en varias líneas).
    requested: Dict[str, int] = {}
    for item in return_data.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Cantidad inválida para el producto {item.barcode}: debe ser mayor a 0")
        requested[item.barcode] = requested.get(item.barcode, 0) + item.quantity

    async def _create(session):
        invoice = await db.invoices.find_one({"invoice_number": return_data.invoice_number}, session=session)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.get("status") == "returned":
            raise HTTPException(status_code=400, detail="Esta factura ya fue devuelta por completo")

        # Lo vendido por producto, con el precio y el IVA con que se facturó.
        sold: Dict[str, Dict[str, Any]] = {}
        for line in invoice.get("items", []):
            entry = sold.setdefault(line["barcode"], {
                "product_name": line["product_name"],
                "unit_price": line["unit_price"],
                "tax_rate": line.get("tax_rate", 0),
                # P2.29: costo de la venta (None en ventas anteriores a que se guardara).
                "unit_cost": line.get("unit_cost"),
                "quantity": 0,
            })
            entry["quantity"] += line["quantity"]

        # Lo ya devuelto en devoluciones anteriores de esta factura.
        returned_before: Dict[str, int] = {}
        previous = await db.returns.find({"invoice_number": return_data.invoice_number}, {"_id": 0, "items": 1}, session=session).to_list(None)
        for ret in previous:
            for line in ret.get("items", []):
                returned_before[line["barcode"]] = returned_before.get(line["barcode"], 0) + line["quantity"]

        return_items = []
        for barcode, qty in requested.items():
            if barcode not in sold:
                raise HTTPException(status_code=400, detail=f"El producto {barcode} no pertenece a la factura {return_data.invoice_number}")
            line = sold[barcode]
            available = line["quantity"] - returned_before.get(barcode, 0)
            if qty > available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se pueden devolver {max(available, 0)} unidad(es) de {line['product_name']} "
                           f"(vendidas {line['quantity']}, ya devueltas {returned_before.get(barcode, 0)})",
                )
            item_subtotal = line["unit_price"] * qty
            item_tax = item_subtotal * line["tax_rate"] / 100
            return_items.append({
                "barcode": barcode,
                "product_name": line["product_name"],
                "quantity": qty,
                "unit_price": line["unit_price"],
                "tax_rate": line["tax_rate"],
                # P2.29: el costo de la venta original, para descontar su ganancia (None en ventas antiguas).
                "unit_cost": line.get("unit_cost"),
                "subtotal": item_subtotal,
                "tax_amount": item_tax,
                "total": item_subtotal + item_tax,
            })

        subtotal_return = sum(i["subtotal"] for i in return_items)
        tax_return = sum(i["tax_amount"] for i in return_items)
        total_return = sum(i["total"] for i in return_items)
        now = now_utc()

        return_dict = {
            "invoice_number": return_data.invoice_number,
            "items": return_items,
            "subtotal": subtotal_return,
            "total_tax": tax_return,
            "total": total_return,
            "created_by": current_user.email,
            "created_at": now
        }
        inserted_return = await db.returns.insert_one(dict(return_dict), session=session)

        # ¿Queda algo sin devolver tras esta devolución?
        fully_returned = all(
            line["quantity"] - returned_before.get(barcode, 0) - requested.get(barcode, 0) <= 0
            for barcode, line in sold.items()
        )

        if fully_returned:
            update_data = {"status": "returned", "subtotal": 0, "total_tax": 0, "total": 0}
        else:
            update_data = {
                "status": "partial_return",
                "subtotal": max(0, invoice.get("subtotal", 0) - subtotal_return),
                "total_tax": max(0, invoice.get("total_tax", 0) - tax_return),
                "total": max(0, invoice.get("total", 0) - total_return),
            }
        new_total = update_data["total"]

        # P2.31 (+ P1.40): lo que el cliente ya pagó por encima del nuevo total se le devuelve en
        # EFECTIVO desde la caja. Cubre los tres casos:
        #   contado → se devuelve lo devuelto · crédito → baja la deuda (no sale dinero)
        #   crédito con abonos de más → se devuelve el excedente.
        amount_paid = float(invoice.get("amount_paid", 0) or 0)
        refund = round(max(0.0, amount_paid - new_total), 2)
        if refund <= _MONEY_EPS:
            refund = 0.0
        new_paid = min(amount_paid, new_total)
        new_balance = new_total - new_paid
        update_data["amount_paid"] = new_paid
        if new_balance <= _MONEY_EPS:
            update_data["balance"] = 0
            if invoice.get("payment_status") == "por_cobrar":
                update_data["payment_status"] = "pagado"
        else:
            update_data["balance"] = new_balance

        refund_session = None
        if refund > 0:
            refund_session = await session_for_money(current_user.email, "refund", refund, session=session)
            await add_movement(refund_session, "refund", "out", CASH_METHOD, refund, current_user.email,
                               reference=return_data.invoice_number, session=session)
        refund_info = {"refund_amount": refund, "refund_method": CASH_METHOD if refund > 0 else None,
                       "cash_session_id": refund_session}
        await db.returns.update_one({"_id": inserted_return.inserted_id}, {"$set": refund_info}, session=session)
        return_dict.update(refund_info)

        await db.invoices.update_one(
            {"invoice_number": return_data.invoice_number},
            {"$set": update_data},
            session=session,
        )

        # Reingreso al inventario y movimientos.
        for item in return_items:
            await db.products.update_one(
                {"barcode": item["barcode"]},
                {"$inc": {"stock": item["quantity"]}},
                session=session,
            )
            await db.inventory_movements.insert_one({
                "barcode": item["barcode"],
                "product_name": item["product_name"],
                "movement_type": "return",
                "quantity": item["quantity"],
                "reference": return_data.invoice_number,
                "created_by": current_user.email,
                "created_at": now
            }, session=session)

        await audit.record("returns", "create", entity_id=return_data.invoice_number, entity_name=invoice.get("client_name"),
                           summary=f"Devolución sobre la factura {return_data.invoice_number} por {total_return:,.0f} "
                                   f"({sum(i['quantity'] for i in return_items)} unidad(es)); la factura queda "
                                   f"{'devuelta por completo' if fully_returned else 'con devolución parcial'}"
                                   + (f"; reembolso en efectivo {refund:,.0f}".replace(",", ".") if refund > 0 else ""),
                           before={k: invoice.get(k) for k in update_data}, after=update_data,
                           details={"items": return_items}, session=session)

        return return_dict

    return_dict = await run_in_transaction(_create)
    return Return(**{**return_dict, "created_at": as_datetime(return_dict["created_at"])})


@router.get("/returns")
async def get_returns(search: Optional[str] = None, invoice_number: Optional[str] = None, pg: dict = Depends(page_params),
                      current_user: User = Depends(require_permission("returns", "read"))):
    """Devoluciones paginadas, más recientes primero (P1.18)."""
    query = combine({"invoice_number": invoice_number} if invoice_number else None,
                    search_filter(search, ["invoice_number", "created_by"]))
    return await paginate(db.returns, query, [("created_at", -1)], **pg)

# ==================== FIOS (CREDITS/PAYMENTS) ====================

FIOS_FILTERS = {
    # P2.30: filtros de la cartera por estado / tramo de antigüedad (se aplican a la cuenta del cliente).
    "overdue": {"overdue_balance": {"$gt": 0}},
    "due_soon": {"due_soon_balance": {"$gt": 0}},
    "current": {"overdue_balance": {"$lte": 0}},
    **{key: {f"buckets.{key}": {"$gt": 0}} for key, *_ in credit.BUCKETS if key != "current"},
}


def _fios_pipeline(search: Optional[str], status: Optional[str], now, settings) -> list:
    if status and status not in FIOS_FILTERS:
        raise HTTPException(status_code=400, detail=f"Filtro de cartera inválido '{status}'. "
                                                    f"Usa: {', '.join(FIOS_FILTERS)}.")
    match = combine({"payment_status": "por_cobrar", "balance": {"$gt": 0}},
                    search_filter(search, ["client_name", "client_document"]))
    soon = credit.due_soon_expr(now, settings["due_soon_days"])
    bucket_sums = {f"b_{key}": {"$sum": {"$cond": [{"$eq": ["$_bucket", key]}, "$balance", 0]}}
                   for key, *_ in credit.BUCKETS if key != "current"}
    return [
        {"$match": match},
        *credit.overdue_stages(now),
        {"$group": {
            "_id": {"client_document": "$client_document", "client_document_type": "$client_document_type"},
            "client_name": {"$last": "$client_name"},
            "total_credit": {"$sum": "$total"},
            "total_paid": {"$sum": "$amount_paid"},
            "balance": {"$sum": "$balance"},
            "invoices_count": {"$sum": 1},
            "overdue_balance": {"$sum": {"$cond": [{"$gt": ["$_od", 0]}, "$balance", 0]}},
            "overdue_invoices": {"$sum": {"$cond": [{"$gt": ["$_od", 0]}, 1, 0]}},
            "due_soon_balance": {"$sum": {"$cond": [soon, "$balance", 0]}},
            "max_days_overdue": {"$max": "$_od"},
            "next_due_date": {"$min": {"$cond": [{"$gt": ["$_od", 0]}, None, "$due_date"]}},
            **bucket_sums,
        }},
        {"$project": {
            "_id": 0,
            "client_document": "$_id.client_document",
            "client_document_type": "$_id.client_document_type",
            "client_name": 1, "total_credit": 1, "total_paid": 1, "balance": 1, "invoices_count": 1,
            "overdue_balance": 1, "overdue_invoices": 1, "due_soon_balance": 1, "max_days_overdue": 1, "next_due_date": 1,
            "buckets": {key: f"$b_{key}" for key, *_ in credit.BUCKETS if key != "current"},
            "credit_status": {"$switch": {"branches": [
                {"case": {"$gt": ["$overdue_balance", 0]}, "then": "overdue"},
                {"case": {"$gt": ["$due_soon_balance", 0]}, "then": "due_soon"}], "default": "current"}},
        }},
        *([{"$match": FIOS_FILTERS[status]}] if status else []),
    ]


def _account_status_label(acc: dict) -> str:
    if acc.get("credit_status") == "overdue":
        d = int(acc.get("max_days_overdue") or 0)
        return f"Vencida ({d} día{'s' if d != 1 else ''})"
    return "Por vencer" if acc.get("credit_status") == "due_soon" else "Al día"


@router.get("/fios")
async def get_fios_accounts(search: Optional[str] = None, status: Optional[str] = None, pg: dict = Depends(page_params),
                            current_user: User = Depends(require_permission("fios", "read"))):
    """Cuentas por cobrar agrupadas por cliente (tipo + número), paginadas (P1.18), con vencimientos
    y antigüedad (P2.30). Primero las más atrasadas, luego por saldo. `status`: overdue · due_soon ·
    current · 1_30 · 31_60 · 61_90 · 90_plus."""
    now = now_utc()
    settings = await credit.get_settings()
    pipeline = _fios_pipeline(search, status, now, settings)
    page = await paginate_pipeline(db.invoices, pipeline,
                                   [("max_days_overdue", -1), ("balance", -1), ("client_document", 1)], **pg)
    for acc in page["items"]:
        acc["credit_status_label"] = _account_status_label(acc)
        for k in ("balance", "overdue_balance", "due_soon_balance", "total_credit", "total_paid"):
            acc[k] = round(acc.get(k) or 0, 2)
    # Totales de la cartera completa (no solo la página ni la búsqueda).
    totals = await db.invoices.aggregate([
        {"$match": {"payment_status": "por_cobrar", "balance": {"$gt": 0}}},
        {"$group": {"_id": {"d": "$client_document", "t": "$client_document_type"},
                    "credit": {"$sum": "$total"}, "paid": {"$sum": "$amount_paid"},
                    "balance": {"$sum": "$balance"}, "n": {"$sum": 1}}},
        {"$group": {"_id": None, "credit": {"$sum": "$credit"}, "paid": {"$sum": "$paid"},
                    "balance": {"$sum": "$balance"}, "n": {"$sum": "$n"}, "clients": {"$sum": 1}}},
    ]).to_list(1)
    t = totals[0] if totals else {}
    page["summary"] = {"total_credit": round(t.get("credit", 0), 2), "total_paid": round(t.get("paid", 0), 2),
                       "balance": round(t.get("balance", 0), 2), "pending_invoices": t.get("n", 0),
                       "clients_count": t.get("clients", 0)}
    page["aging"] = await credit.aging_summary(settings=settings)   # P2.30: tramos de antigüedad
    page["settings"] = settings
    return page


@router.get("/fios/export")
async def export_fios_accounts(search: Optional[str] = None, status: Optional[str] = None, format: str = "csv",
                               tz_offset_minutes: int = 0, current_user: User = Depends(require_permission("fios", "read"))):
    """P2.30: cartera completa (con el filtro activo), con antigüedad por tramo. P2.33: csv · xlsx · pdf."""
    from core.exporting import check_format
    if check_format(format) != "csv":
        from routers.exports import fios_report
        return await fios_report(search, status, current_user, format, tz_offset_minutes)
    now = now_utc()
    settings = await credit.get_settings()
    rows = await db.invoices.aggregate(
        _fios_pipeline(search, status, now, settings) + [{"$sort": {"max_days_overdue": -1, "balance": -1}}]
    ).to_list(None)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    labels = [label for key, label, *_ in credit.BUCKETS if key != "current"]
    w.writerow(["Tipo doc.", "Documento", "Cliente", "Facturas", "Total crédito", "Abonado", "Saldo", "Vencido",
                "Por vencer", "Días máx. de atraso", "Próximo vencimiento", "Estado", *labels])
    for a in rows:
        nd = a.get("next_due_date")
        w.writerow([a.get("client_document_type") or "", a["client_document"], a.get("client_name", ""), a["invoices_count"],
                    round(a["total_credit"], 2), round(a["total_paid"], 2), round(a["balance"], 2),
                    round(a["overdue_balance"], 2), round(a["due_soon_balance"], 2), int(a.get("max_days_overdue") or 0),
                    (as_datetime(nd) - timedelta(minutes=credit.BUSINESS_TZ_OFFSET_MINUTES)).strftime("%Y-%m-%d") if nd else "",
                    _account_status_label(a),
                    *[round(a["buckets"].get(key, 0), 2) for key, *_ in credit.BUCKETS if key != "current"]])
    data = "\ufeff" + out.getvalue()   # BOM: Excel abre bien las tildes
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=cartera_{now.strftime('%Y%m%d')}.csv"})


@router.get("/fios/{client_document}")
async def get_fios_client_detail(client_document: str, document_type: Optional[str] = None,
                                 current_user: User = Depends(require_permission("fios", "read"))):
    """Obtener detalle de cuentas por cobrar de un cliente específico (tipo + número, P1.15)"""
    client = await resolve_client(client_document, document_type)

    # Get pending invoices for this client
    invoices = await db.invoices.find({
        **invoices_of_client_query(client),
        "payment_status": "por_cobrar",
        "balance": {"$gt": 0}
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    # Get payment history for this client's invoices
    invoice_numbers = [inv["invoice_number"] for inv in invoices]
    payments = await db.fio_payments.find({
        "invoice_number": {"$in": invoice_numbers}
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    # P2.30: estado de cada factura (al día / por vencer / vencida con días de atraso).
    settings = await credit.get_settings()
    now = now_utc()
    for inv in invoices:
        inv.update(credit.invoice_status(inv.get("due_date"), settings["due_soon_days"], now))
    invoices.sort(key=lambda i: (as_datetime(i["due_date"]) if i.get("due_date") else now, i["invoice_number"]))

    # Calculate totals
    total_credit = sum(inv["total"] for inv in invoices)
    total_paid = sum(inv["amount_paid"] for inv in invoices)
    total_balance = sum(inv["balance"] for inv in invoices)

    return {
        "client": {
            "document_number": client["document_number"],
            "document_type": client.get("document_type"),
            "name": f"{client['first_name']} {client['last_name']}",
            "phone": client.get("phone"),
            "email": client.get("email")
        },
        "summary": {
            "total_credit": total_credit,
            "total_paid": total_paid,
            "balance": total_balance,
            "invoices_count": len(invoices),
            "overdue_balance": round(sum(i["balance"] for i in invoices if i["credit_status"] == "overdue"), 2),
            "overdue_invoices": sum(1 for i in invoices if i["credit_status"] == "overdue"),
            "max_days_overdue": max([i["days_overdue"] for i in invoices] or [0]),
        },
        "credit": {"credit_days": client.get("credit_days"), "credit_limit": client.get("credit_limit"),
                   "term_days": credit.term_for_client(client, settings),
                   "available": round(float(client["credit_limit"]) - total_balance, 2) if client.get("credit_limit") else None},
        "invoices": invoices,
        "payment_history": payments
    }

@router.get("/fios/invoice/{invoice_number}")
async def get_fios_invoice_detail(invoice_number: str, current_user: User = Depends(require_permission("fios", "read"))):
    """Obtener detalle de una factura por cobrar específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if invoice.get("payment_status") != "por_cobrar":
        raise HTTPException(status_code=400, detail="Esta factura no es una cuenta por cobrar")

    # Get payment history for this invoice
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    return {
        "invoice": invoice,
        "payments": payments
    }

@router.post("/fios/{invoice_number}/payment")
async def register_fio_payment(
    invoice_number: str,
    payment: FioPaymentCreate,
    current_user: User = Depends(require_permission("fios", "create"))
):
    """Registrar un abono a una factura por cobrar"""
    if payment.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto del abono debe ser mayor a 0")

    async def _register(session):
        # Get the invoice
        invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0}, session=session)
        if not invoice:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        if invoice.get("payment_status") != "por_cobrar":
            raise HTTPException(status_code=400, detail="Esta factura no es una cuenta por cobrar")

        # Validate payment method is active
        payment_method = await db.payment_methods.find_one(
            {"name": payment.payment_method, "is_active": True}, session=session
        )
        if not payment_method:
            raise HTTPException(status_code=400, detail="La forma de pago seleccionada no existe o no está activa")

        # Validate payment amount
        current_balance = invoice.get("balance", invoice["total"])
        if payment.amount > current_balance:
            raise HTTPException(status_code=400, detail=f"El monto del abono (${payment.amount:,.2f}) excede el saldo pendiente (${current_balance:,.2f})")

        # P2.31: caja de quien recibe el abono.
        cash_session_id = await session_for_money(current_user.email, "fio_payment", session=session)

        # Create payment record
        payment_dict = {
            "payment_id": f"PAY-{uuid.uuid4().hex[:8].upper()}",
            "invoice_number": invoice_number,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "notes": payment.notes,
            "created_by": current_user.email,
            "created_at": now_utc()
        }

        payment_dict["cash_session_id"] = cash_session_id
        await db.fio_payments.insert_one(dict(payment_dict), session=session)
        await add_movement(cash_session_id, "fio_payment", "in", payment.payment_method, payment.amount,
                           current_user.email, reference=invoice_number, session=session)

        # Update invoice balance
        new_amount_paid = invoice.get("amount_paid", 0) + payment.amount
        new_balance = invoice["total"] - new_amount_paid

        # If fully paid, update payment_status
        update_data = {
            "amount_paid": new_amount_paid,
            "balance": new_balance
        }

        if new_balance <= 0:
            update_data["payment_status"] = "pagado"
            update_data["payment_method"] = payment.payment_method  # Last payment method used

        await db.invoices.update_one(
            {"invoice_number": invoice_number},
            {"$set": update_data},
            session=session,
        )

        await audit.record("fios", "create", entity_id=invoice_number, entity_name=invoice.get("client_name"),
                           summary=f"Abono de {payment.amount:,.0f} ({payment.payment_method}) a la factura {invoice_number}; "
                                   f"saldo {current_balance:,.0f} → {new_balance:,.0f}"
                                   + (" (pagada)" if new_balance <= 0 else ""),
                           before={k: invoice.get(k) for k in update_data}, after=update_data,
                           details=payment_dict, session=session)

        return payment_dict, new_amount_paid, new_balance

    payment_response, new_amount_paid, new_balance = await run_in_transaction(_register)

    return {
        "message": "Abono registrado exitosamente",
        "payment": payment_response,
        "invoice_update": {
            "invoice_number": invoice_number,
            "new_amount_paid": new_amount_paid,
            "new_balance": new_balance,
            "fully_paid": new_balance <= 0
        }
    }


@router.get("/fios/payments/{invoice_number}")
async def get_invoice_payments(invoice_number: str, current_user: User = Depends(require_any_permission(("fios", "read"), ("invoices", "read")))):
    """Obtener historial de pagos de una factura"""
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(None)

    return payments

# ==================== INVOICES ENHANCED (WITH PDF TICKETS) ====================

@router.get("/pos/invoices")
async def get_pos_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client_document: Optional[str] = None,
    user_email: Optional[str] = None,
    invoice_number: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    page_size: Optional[int] = Query(None, ge=1, le=200),
    tz_offset_minutes: int = 0,
    current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))
):
    """Listar facturas POS con filtros y paginación"""
    query = {}

    # P1.14: días locales completos (antes se cortaba a las 23:59:59 UTC = 6:59 p. m. en Colombia).
    rng = created_at_range(start_date, end_date, tz_offset_minutes)
    if rng:
        query["created_at"] = rng

    if client_document:
        query["client_document"] = {"$regex": re.escape(client_document), "$options": "i"}

    if user_email:
        query["created_by"] = {"$regex": re.escape(user_email), "$options": "i"}

    if invoice_number:
        query["invoice_number"] = {"$regex": re.escape(invoice_number), "$options": "i"}

    if status:
        query["status"] = status

    # P1.18: formato común {items, total, page, page_size, pages} (como el resto de listados).
    # `page_size` reemplaza a `limit`; se conservan "invoices" y "pagination" por compatibilidad.
    size = page_size or limit
    result = await paginate(db.invoices, query, [("created_at", -1)], page=page, page_size=size)
    result["invoices"] = result["items"]
    result["pagination"] = {"page": page, "limit": size, "total": result["total"], "pages": result["pages"]}
    return result

@router.get("/pos/invoices/{invoice_number}")
async def get_pos_invoice_detail(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))):
    """Obtener detalle de una factura específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice

@router.get("/pos/invoices/{invoice_number}/ticket")
async def get_invoice_ticket(invoice_number: str, current_user: User = Depends(require_any_permission(("invoices", "read"), ("pos", "read")))):
    """Generar y descargar ticket PDF de una factura"""
    # Get invoice
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # Get ticket config
    config = await db.ticket_config.find_one({}, {"_id": 0})
    if not config:
        config = {
            "company_name": "Mi Empresa",
            "nit": "",
            "phone": "",
            "email": "",
            "address": "",
            "ticket_width": 80,
            "footer_message": "¡Gracias por su compra!"
        }

    # Get returns for this invoice
    returns = await db.returns.find({"invoice_number": invoice_number}, {"_id": 0}).to_list(100)

    # Create PDF generator
    generator = TicketPDFGenerator(ticket_width=config.get("ticket_width", 80))

    # Prepare invoice data for the generator
    invoice_data = {
        "invoice_number": invoice["invoice_number"],
        "client_name": invoice.get("client_name", "Cliente General"),
        "client_document": invoice.get("client_document", ""),
        "client_document_type": invoice.get("client_document_type") or "",
        "items": invoice.get("items", []),
        "subtotal": invoice.get("subtotal", 0),
        "total_tax": invoice.get("total_tax", 0),
        "total": invoice.get("total", 0),
        "created_at": invoice.get("created_at"),
        "created_by": invoice.get("created_by", ""),
        "returns": returns  # Include returns data
    }

    # Generate PDF
    pdf_buffer = generator.generate_ticket(invoice_data, config)

    # Return as downloadable PDF
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ticket_{invoice_number}.pdf"
        }
    )

