"""Ventas (POS): crear una factura de contado o a crédito (mantenimiento fase 3)."""
from datetime import timedelta
from core.errors import BusinessError
from core.dates import now_utc, as_datetime
from core.database import db
from repositories import invoices as invoices_repo
from repositories import products as products_repo
from core.transactions import run_in_transaction
from core.counters import INVOICE_COUNTER, ensure_counter, next_number
from models.auth import User
from models.billing import InvoiceCreate

from core import audit
from repositories.clients import resolve_client
from core.pricing import unit_price_for
from core.cash import add_movement, session_for_money
from core import credit
from core.money import money


async def create_sale(invoice_data: InvoiceCreate, current_user: User):
    """Crea la factura en una transacción: valida pago y productos, precio de la lista del cliente (P1.17),
    IVA por producto (P1.16), cupo y vencimiento si es a crédito (P2.30), caja del vendedor (P2.31),
    descuento atómico de stock, movimientos, auditoría y aviso de bajo stock (P2.34).
    Devuelve el dict de la factura (con `stock_warnings`)."""
    # Validate payment_status
    if invoice_data.payment_status not in ["pagado", "por_cobrar"]:
        raise BusinessError("Estado de pago inválido. Use 'pagado' o 'por_cobrar'")

    # If payment_status is "pagado", payment_method is required
    if invoice_data.payment_status == "pagado" and not invoice_data.payment_method:
        raise BusinessError("La forma de pago es obligatoria cuando el estado es 'pagado'")

    if not invoice_data.items:
        raise BusinessError("La factura debe tener al menos un producto")
    # Una cantidad cero o negativa no es una venta (y con -N el descuento de stock lo SUMARÍA).
    for req_item in invoice_data.items:
        if req_item.quantity <= 0:
            raise BusinessError(f"Cantidad inválida para el producto {req_item.barcode}: debe ser mayor a 0")

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
                raise BusinessError("La forma de pago seleccionada no existe o no está activa")

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
            product = await products_repo.get(req_item.barcode, session=session)
            if not product:
                raise BusinessError(f"Producto con código {req_item.barcode} no encontrado")

            # Chequeo temprano para dar un error claro; la garantía real es el descuento
            # condicionado más abajo (el stock puede cambiar entre esta lectura y la escritura).
            if req_item.quantity > product.get("stock", 0):
                raise BusinessError(f"Stock insuficiente para {product['name']}")

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

        await invoices_repo.insert(invoice_dict, session=session)
        if invoice_data.payment_status == "pagado" and total > 0:
            await add_movement(cash_session_id, "sale", "in", invoice_dict["payment_method"], total,
                               current_user.email, reference=invoice_number, session=session)

        # Update inventory and create movements
        for item in processed_items:
            # Descuento atómico: solo se aplica si queda stock suficiente EN ESE INSTANTE.
            # Con ventas concurrentes (o la misma referencia repetida en la factura) el stock
            # nunca baja de 0; si no alcanza, la excepción aborta toda la transacción.
            if not await products_repo.take_stock(item["barcode"], item["quantity"], session=session):
                raise BusinessError(f"Stock insuficiente para {item['product_name']}")
            await products_repo.record_movement(barcode=item["barcode"], product_name=item["product_name"], movement_type="sale",
                                                quantity=-item["quantity"], reference=invoice_number,
                                                created_by=current_user.email, created_at=now, session=session)

        # Bitácora en la misma transacción: si la venta se revierte, el registro también.
        pago = ("de contado (" + str(invoice_dict.get("payment_method")) + ")") if invoice_data.payment_status == "pagado" \
            else f"a crédito (vence {(due_date - timedelta(minutes=offset)).strftime('%d/%m/%Y')})"
        await audit.record("invoices", "create", entity_id=invoice_number, entity_name=client_name,
                           summary=f"Venta {invoice_number} a '{client_name}' por {money(total)} {pago}, "
                                   f"{sum(i['quantity'] for i in processed_items)} unidad(es)",
                           after=invoice_dict, session=session)

        return invoice_dict

    invoice_dict = await run_in_transaction(_create)
    # P2.34: aviso en el POS de lo que quedó en bajo stock o agotado con esta venta.
    from core.alerts import stock_warnings
    warnings = await stock_warnings([i["barcode"] for i in invoice_dict["items"]])
    return {**invoice_dict, "created_at": as_datetime(invoice_dict["created_at"]), "stock_warnings": warnings}
