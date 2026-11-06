"""Cartera (Fios): pipeline de cuentas por cobrar con vencimientos y antigüedad (P2.30).
Lo usan routers/fios.py y la exportación (mantenimiento fase 3)."""
from typing import Optional

from core import credit
from core.errors import BusinessError, NotFoundError
from core.pagination import combine, search_filter
from core.dates import now_utc, as_datetime
from core.database import db
from repositories import invoices as invoices_repo
from core.transactions import run_in_transaction
import uuid
from models.auth import User
from models.billing import FioPaymentCreate

from core import audit
from repositories.clients import resolve_client, invoices_of_client_query
from core.cash import add_movement, session_for_money
from core.pagination import paginate_pipeline


FIOS_FILTERS = {
    # P2.30: filtros de la cartera por estado / tramo de antigüedad (se aplican a la cuenta del cliente).
    "overdue": {"overdue_balance": {"$gt": 0}},
    "due_soon": {"due_soon_balance": {"$gt": 0}},
    "current": {"overdue_balance": {"$lte": 0}},
    **{key: {f"buckets.{key}": {"$gt": 0}} for key, *_ in credit.BUCKETS if key != "current"},
}


def fios_pipeline(search: Optional[str], status: Optional[str], now, settings) -> list:
    if status and status not in FIOS_FILTERS:
        raise BusinessError(f"Filtro de cartera inválido '{status}'. Usa: {', '.join(FIOS_FILTERS)}.")
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


def account_status_label(acc: dict) -> str:
    if acc.get("credit_status") == "overdue":
        d = int(acc.get("max_days_overdue") or 0)
        return f"Vencida ({d} día{'s' if d != 1 else ''})"
    return "Por vencer" if acc.get("credit_status") == "due_soon" else "Al día"


async def accounts_page(search: Optional[str], status: Optional[str], pg: dict, current_user: User):
    """Cuentas por cobrar agrupadas por cliente (tipo + número), paginadas (P1.18), con vencimientos
    y antigüedad (P2.30). Primero las más atrasadas, luego por saldo. `status`: overdue · due_soon ·
    current · 1_30 · 31_60 · 61_90 · 90_plus."""
    now = now_utc()
    settings = await credit.get_settings()
    pipeline = fios_pipeline(search, status, now, settings)
    page = await paginate_pipeline(db.invoices, pipeline,
                                   [("max_days_overdue", -1), ("balance", -1), ("client_document", 1)], **pg)
    for acc in page["items"]:
        acc["credit_status_label"] = account_status_label(acc)
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


async def client_detail(client_document: str, document_type: Optional[str], current_user: User):
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


async def register_payment(invoice_number: str, payment: FioPaymentCreate, current_user: User):
    """Registrar un abono a una factura por cobrar"""
    if payment.amount <= 0:
        raise BusinessError("El monto del abono debe ser mayor a 0")

    async def _register(session):
        # Get the invoice
        invoice = await invoices_repo.get(invoice_number, session=session)
        if not invoice:
            raise NotFoundError("Factura no encontrada")

        if invoice.get("payment_status") != "por_cobrar":
            raise BusinessError("Esta factura no es una cuenta por cobrar")

        # Validate payment method is active
        payment_method = await db.payment_methods.find_one(
            {"name": payment.payment_method, "is_active": True}, session=session
        )
        if not payment_method:
            raise BusinessError("La forma de pago seleccionada no existe o no está activa")

        # Validate payment amount
        current_balance = invoice.get("balance", invoice["total"])
        if payment.amount > current_balance:
            raise BusinessError(f"El monto del abono (${payment.amount:,.2f}) excede el saldo pendiente (${current_balance:,.2f})")

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

        await invoices_repo.update(invoice_number, update_data, session=session)

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
