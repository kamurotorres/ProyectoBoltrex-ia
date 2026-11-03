from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request, Response, BackgroundTasks
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from core.database import db
from core.database import get_db
from core.security import get_current_user, get_password_hash, verify_password, create_access_token
from models.auth import *
from models.billing import *
from models.inventory import *
from models.entities import *
import pandas as pd
import io
import csv
from fastapi.responses import StreamingResponse
from ticket_generator import TicketPDFGenerator

router = APIRouter(tags=["Billing"])
db_dep = Depends(get_db)
# ==================== TAX RATES ====================

@router.post("/tax-rates", response_model=TaxRate)
async def create_tax_rate(tax_rate: TaxRateCreate, current_user: User = Depends(get_current_user)):
    if tax_rate.is_active:
        await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    
    tr_dict = tax_rate.model_dump()
    if tr_dict.get("effective_date"):
        tr_dict["effective_date"] = tr_dict["effective_date"].isoformat()
    else:
        tr_dict["effective_date"] = datetime.now(timezone.utc).isoformat()
    tr_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tax_rates.insert_one(tr_dict)
    return TaxRate(**{**tr_dict, "effective_date": datetime.fromisoformat(tr_dict["effective_date"]), "created_at": datetime.fromisoformat(tr_dict["created_at"])})

@router.get("/tax-rates", response_model=List[TaxRate])
async def get_tax_rates(current_user: User = Depends(get_current_user)):
    tax_rates = await db.tax_rates.find({}, {"_id": 0}).to_list(1000)
    for tr in tax_rates:
        if isinstance(tr.get('effective_date'), str):
            tr['effective_date'] = datetime.fromisoformat(tr['effective_date'])
        if isinstance(tr.get('created_at'), str):
            tr['created_at'] = datetime.fromisoformat(tr['created_at'])
    return tax_rates

@router.patch("/tax-rates/{name}/activate")
async def activate_tax_rate(name: str, current_user: User = Depends(get_current_user)):
    await db.tax_rates.update_many({"is_active": True}, {"$set": {"is_active": False}})
    result = await db.tax_rates.update_one({"name": name}, {"$set": {"is_active": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    return {"message": "Tax rate activated"}

# ==================== PAYMENT METHODS ====================

@router.post("/payment-methods", response_model=PaymentMethod)
async def create_payment_method(payment_method: PaymentMethodCreate, current_user: User = Depends(get_current_user)):
    """Crear una nueva forma de pago"""
    existing = await db.payment_methods.find_one({"name": payment_method.name})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")
    
    pm_dict = payment_method.model_dump()
    pm_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.payment_methods.insert_one(pm_dict)
    return PaymentMethod(**pm_dict)

@router.get("/payment-methods", response_model=List[PaymentMethod])
async def get_payment_methods(current_user: User = Depends(get_current_user)):
    """Listar todas las formas de pago"""
    payment_methods = await db.payment_methods.find({}, {"_id": 0}).to_list(1000)
    for pm in payment_methods:
        if isinstance(pm.get('created_at'), str):
            pm['created_at'] = datetime.fromisoformat(pm['created_at'])
    return payment_methods

@router.get("/payment-methods/active", response_model=List[PaymentMethod])
async def get_active_payment_methods(current_user: User = Depends(get_current_user)):
    """Listar solo formas de pago activas (para POS y Fios)"""
    payment_methods = await db.payment_methods.find({"is_active": True}, {"_id": 0}).to_list(1000)
    for pm in payment_methods:
        if isinstance(pm.get('created_at'), str):
            pm['created_at'] = datetime.fromisoformat(pm['created_at'])
    return payment_methods

@router.put("/payment-methods/{name}", response_model=PaymentMethod)
async def update_payment_method(name: str, payment_method: PaymentMethodUpdate, current_user: User = Depends(get_current_user)):
    """Actualizar una forma de pago"""
    update_data = {k: v for k, v in payment_method.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    
    # Check if new name already exists (if changing name)
    if "name" in update_data and update_data["name"] != name:
        existing = await db.payment_methods.find_one({"name": update_data["name"]})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe una forma de pago con ese nombre")
    
    result = await db.payment_methods.update_one({"name": name}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    
    # Get updated (use new name if changed)
    new_name = update_data.get("name", name)
    updated = await db.payment_methods.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return PaymentMethod(**updated)

@router.delete("/payment-methods/{name}")
async def delete_payment_method(name: str, current_user: User = Depends(get_current_user)):
    """Eliminar una forma de pago"""
    # Check if payment method is being used in any invoice
    usage = await db.invoices.find_one({"payment_method": name})
    if usage:
        raise HTTPException(status_code=400, detail="No se puede eliminar: esta forma de pago está siendo utilizada en facturas")
    
    result = await db.payment_methods.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    return {"message": "Forma de pago eliminada"}

# ==================== INVOICES (POS) ====================

@router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice_data: InvoiceCreate, current_user: User = Depends(get_current_user)):
    # Validate payment_status
    if invoice_data.payment_status not in ["pagado", "por_cobrar"]:
        raise HTTPException(status_code=400, detail="Estado de pago inválido. Use 'pagado' o 'por_cobrar'")
    
    # If payment_status is "pagado", payment_method is required
    if invoice_data.payment_status == "pagado":
        if not invoice_data.payment_method:
            raise HTTPException(status_code=400, detail="La forma de pago es obligatoria cuando el estado es 'pagado'")
        
        # Verify payment method exists and is active
        payment_method = await db.payment_methods.find_one({
            "name": invoice_data.payment_method,
            "is_active": True
        })
        if not payment_method:
            raise HTTPException(status_code=400, detail="La forma de pago seleccionada no existe o no está activa")
    
    # Get client
    client = await db.clients.find_one({"document_number": invoice_data.client_document}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client_name = f"{client['first_name']} {client['last_name']}"
    client_price_list = client.get("price_list", "default")
    
    processed_items = []
    subtotal = 0.0
    total_tax = 0.0
    total = 0.0

    # Calculate totals securely on the server
    for req_item in invoice_data.items:
        product = await db.products.find_one({"barcode": req_item.barcode})
        if not product:
            raise HTTPException(status_code=400, detail=f"Producto con código {req_item.barcode} no encontrado")
        
        if req_item.quantity > product.get("stock", 0):
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product['name']}")

        # Determine price based on price list
        unit_price = product["purchase_price"] * 1.3
        if client_price_list and "prices" in product:
            for pl in product["prices"]:
                if pl["price_list_name"] == client_price_list:
                    unit_price = pl["price"]
                    break

        item_subtotal = unit_price * req_item.quantity
        item_tax_amount = (item_subtotal * product["tax_rate"]) / 100
        item_total = item_subtotal + item_tax_amount

        subtotal += item_subtotal
        total_tax += item_tax_amount
        total += item_total

        processed_items.append({
            "barcode": product["barcode"],
            "product_name": product["name"],
            "quantity": req_item.quantity,
            "unit_price": unit_price,
            "tax_rate": product["tax_rate"],
            "subtotal": item_subtotal,
            "tax_amount": item_tax_amount,
            "total": item_total
        })

    # Atomic invoice number generation
    counter = await db.counters.find_one({"_id": "invoice_id"})
    if not counter:
        last_invoice = await db.invoices.find_one({}, {"_id": 0, "invoice_number": 1}, sort=[("created_at", -1)])
        if last_invoice:
            last_num = int(last_invoice["invoice_number"].split("-")[1])
            await db.counters.insert_one({"_id": "invoice_id", "seq": last_num})
        else:
            await db.counters.insert_one({"_id": "invoice_id", "seq": 0})
            
    counter = await db.counters.find_one_and_update(
        {"_id": "invoice_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    invoice_number = f"INV-{counter['seq']:06d}"
    
    # Determine amount_paid and balance based on payment_status
    if invoice_data.payment_status == "pagado":
        amount_paid = total
        balance = 0
    else:  # por_cobrar
        amount_paid = 0
        balance = total
    
    invoice_dict = {
        "invoice_number": invoice_number,
        "client_document": invoice_data.client_document,
        "client_name": client_name,
        "items": processed_items,
        "subtotal": subtotal,
        "total_tax": total_tax,
        "total": total,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "payment_status": invoice_data.payment_status,
        "payment_method": invoice_data.payment_method if invoice_data.payment_status == "pagado" else None,
        "amount_paid": amount_paid,
        "balance": balance
    }
    
    await db.invoices.insert_one(invoice_dict)
    
    # Update inventory and create movements
    for item in processed_items:
        await db.products.update_one(
            {"barcode": item["barcode"]},
            {"$inc": {"stock": -item["quantity"]}}
        )
        
        movement_dict = {
            "barcode": item["barcode"],
            "product_name": item["product_name"],
            "movement_type": "sale",
            "quantity": -item["quantity"],
            "reference": invoice_number,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    return Invoice(**{**invoice_dict, "created_at": datetime.fromisoformat(invoice_dict["created_at"])})

@router.get("/invoices", response_model=List[Invoice])
async def get_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for inv in invoices:
        if isinstance(inv.get('created_at'), str):
            inv['created_at'] = datetime.fromisoformat(inv['created_at'])
    return invoices

@router.get("/invoices/{invoice_number}")
async def get_invoice(invoice_number: str, current_user: User = Depends(get_current_user)):
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

@router.post("/returns", response_model=Return)
async def create_return(return_data: ReturnCreate, current_user: User = Depends(get_current_user)):
    # Verify invoice exists
    invoice = await db.invoices.find_one({"invoice_number": return_data.invoice_number})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    total_return = sum(item.total for item in return_data.items)
    
    return_dict = {
        "invoice_number": return_data.invoice_number,
        "items": [item.model_dump() for item in return_data.items],
        "total": total_return,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.returns.insert_one(return_dict)
    
    # Calculate new invoice totals after return
    original_total = invoice.get("total", 0)
    
    # New total after return
    new_total = original_total - total_return
    
    # Prepare update data
    update_data = {}
    
    if new_total <= 0:
        update_data["status"] = "returned"
        update_data["total"] = 0
    else:
        update_data["status"] = "partial_return"
        update_data["total"] = new_total
    
    # Handle "por_cobrar" invoices - update balance in Fios
    if invoice.get("payment_status") == "por_cobrar":
        amount_paid = invoice.get("amount_paid", 0)
        
        # Calculate new balance: new_total - amount_already_paid
        new_balance = max(0, new_total - amount_paid)
        
        update_data["balance"] = new_balance
        
        # If balance is 0 or less, mark as paid
        if new_balance <= 0:
            update_data["payment_status"] = "pagado"
            update_data["balance"] = 0
            # If there was overpayment due to return, adjust amount_paid
            if amount_paid > new_total:
                update_data["amount_paid"] = max(0, new_total)
    
    # Update invoice
    await db.invoices.update_one(
        {"invoice_number": return_data.invoice_number},
        {"$set": update_data}
    )
    
    # Update inventory and create movements
    for item in return_data.items:
        await db.products.update_one(
            {"barcode": item.barcode},
            {"$inc": {"stock": item.quantity}}
        )
        
        movement_dict = {
            "barcode": item.barcode,
            "product_name": item.product_name,
            "movement_type": "return",
            "quantity": item.quantity,
            "reference": return_data.invoice_number,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    return Return(**{**return_dict, "created_at": datetime.fromisoformat(return_dict["created_at"])})

@router.get("/returns", response_model=List[Return])
async def get_returns(current_user: User = Depends(get_current_user)):
    returns = await db.returns.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for ret in returns:
        if isinstance(ret.get('created_at'), str):
            ret['created_at'] = datetime.fromisoformat(ret['created_at'])
    return returns

# ==================== FIOS (CREDITS/PAYMENTS) ====================

@router.get("/fios")
async def get_fios_accounts(current_user: User = Depends(get_current_user)):
    """Obtener resumen de cuentas por cobrar por cliente"""
    # Get all invoices with payment_status "por_cobrar" and balance > 0
    pipeline = [
        {"$match": {"payment_status": "por_cobrar", "balance": {"$gt": 0}}},
        {"$group": {
            "_id": {"client_document": "$client_document", "client_name": "$client_name"},
            "total_credit": {"$sum": "$total"},
            "total_paid": {"$sum": "$amount_paid"},
            "balance": {"$sum": "$balance"},
            "invoices_count": {"$sum": 1}
        }},
        {"$project": {
            "_id": 0,
            "client_document": "$_id.client_document",
            "client_name": "$_id.client_name",
            "total_credit": 1,
            "total_paid": 1,
            "balance": 1,
            "invoices_count": 1
        }},
        {"$sort": {"balance": -1}}
    ]
    
    accounts = await db.invoices.aggregate(pipeline).to_list(1000)
    return accounts

@router.get("/fios/{client_document}")
async def get_fios_client_detail(client_document: str, current_user: User = Depends(get_current_user)):
    """Obtener detalle de cuentas por cobrar de un cliente específico"""
    # Get client info
    client = await db.clients.find_one({"document_number": client_document}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Get pending invoices for this client
    invoices = await db.invoices.find({
        "client_document": client_document,
        "payment_status": "por_cobrar",
        "balance": {"$gt": 0}
    }, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Get payment history for this client's invoices
    invoice_numbers = [inv["invoice_number"] for inv in invoices]
    payments = await db.fio_payments.find({
        "invoice_number": {"$in": invoice_numbers}
    }, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Calculate totals
    total_credit = sum(inv["total"] for inv in invoices)
    total_paid = sum(inv["amount_paid"] for inv in invoices)
    total_balance = sum(inv["balance"] for inv in invoices)
    
    return {
        "client": {
            "document_number": client["document_number"],
            "name": f"{client['first_name']} {client['last_name']}",
            "phone": client.get("phone"),
            "email": client.get("email")
        },
        "summary": {
            "total_credit": total_credit,
            "total_paid": total_paid,
            "balance": total_balance,
            "invoices_count": len(invoices)
        },
        "invoices": invoices,
        "payment_history": payments
    }

@router.get("/fios/invoice/{invoice_number}")
async def get_fios_invoice_detail(invoice_number: str, current_user: User = Depends(get_current_user)):
    """Obtener detalle de una factura por cobrar específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    if invoice.get("payment_status") != "por_cobrar":
        raise HTTPException(status_code=400, detail="Esta factura no es una cuenta por cobrar")
    
    # Get payment history for this invoice
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    return {
        "invoice": invoice,
        "payments": payments
    }

@router.post("/fios/{invoice_number}/payment")
async def register_fio_payment(
    invoice_number: str, 
    payment: FioPaymentCreate, 
    current_user: User = Depends(get_current_user)
):
    """Registrar un abono a una factura por cobrar"""
    # Get the invoice
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    if invoice.get("payment_status") != "por_cobrar":
        raise HTTPException(status_code=400, detail="Esta factura no es una cuenta por cobrar")
    
    # Validate payment method is active
    payment_method = await db.payment_methods.find_one({
        "name": payment.payment_method,
        "is_active": True
    })
    if not payment_method:
        raise HTTPException(status_code=400, detail="La forma de pago seleccionada no existe o no está activa")
    
    # Validate payment amount
    current_balance = invoice.get("balance", invoice["total"])
    if payment.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto del abono debe ser mayor a 0")
    if payment.amount > current_balance:
        raise HTTPException(status_code=400, detail=f"El monto del abono (${payment.amount:,.2f}) excede el saldo pendiente (${current_balance:,.2f})")
    
    # Generate payment ID
    import uuid
    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    
    # Create payment record
    payment_dict = {
        "payment_id": payment_id,
        "invoice_number": invoice_number,
        "amount": payment.amount,
        "payment_method": payment.payment_method,
        "notes": payment.notes,
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.fio_payments.insert_one(payment_dict)
    
    # Remove _id added by MongoDB for response
    payment_response = {k: v for k, v in payment_dict.items() if k != '_id'}
    
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
        {"$set": update_data}
    )
    
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
async def get_invoice_payments(invoice_number: str, current_user: User = Depends(get_current_user)):
    """Obtener historial de pagos de una factura"""
    payments = await db.fio_payments.find({
        "invoice_number": invoice_number
    }, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
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
    current_user: User = Depends(get_current_user)
):
    """Listar facturas POS con filtros y paginación"""
    query = {}
    
    # Apply filters
    if start_date:
        if "created_at" not in query:
            query["created_at"] = {}
        query["created_at"]["$gte"] = start_date
    
    if end_date:
        if "created_at" not in query:
            query["created_at"] = {}
        query["created_at"]["$lte"] = end_date + "T23:59:59"
    
    if client_document:
        query["client_document"] = {"$regex": client_document, "$options": "i"}
    
    if user_email:
        query["created_by"] = {"$regex": user_email, "$options": "i"}
    
    if invoice_number:
        query["invoice_number"] = {"$regex": invoice_number, "$options": "i"}
    
    if status:
        query["status"] = status
    
    # Get total count for pagination
    total = await db.invoices.count_documents(query)
    
    # Calculate skip
    skip = (page - 1) * limit
    
    # Get invoices
    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Parse dates
    for inv in invoices:
        if isinstance(inv.get('created_at'), str):
            inv['created_at'] = inv['created_at']
    
    return {
        "invoices": invoices,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@router.get("/pos/invoices/{invoice_number}")
async def get_pos_invoice_detail(invoice_number: str, current_user: User = Depends(get_current_user)):
    """Obtener detalle de una factura específica"""
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice

@router.get("/pos/invoices/{invoice_number}/ticket")
async def get_invoice_ticket(invoice_number: str, current_user: User = Depends(get_current_user)):
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

