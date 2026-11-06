"""Devoluciones validadas contra la factura, con reembolso desde la caja (mantenimiento fase 3)."""
from typing import Dict, Any
from core.errors import BusinessError, NotFoundError
from core.dates import now_utc, as_datetime
from core.database import db
from repositories import invoices as invoices_repo
from repositories import products as products_repo
from core.transactions import run_in_transaction
from models.auth import User
from models.billing import ReturnCreate

from core import audit
from core.cash import CASH_METHOD, add_movement, session_for_money


_MONEY_EPS = 0.005   # tolerancia en pesos al comparar montos


async def create_return(return_data: ReturnCreate, current_user: User):
    """Registrar una devolución validada contra la factura original.

    - Cada producto debe estar en la factura y la cantidad debe ser > 0 y no superar
      lo vendido menos lo ya devuelto en devoluciones anteriores.
    - Precio unitario e IVA se toman de la factura; el importe lo calcula el servidor.
    - Se recalculan subtotal, IVA y total de la factura (y el saldo si es a crédito).
    """
    if not return_data.items:
        raise BusinessError("Selecciona al menos un producto para devolver")

    # Cantidades pedidas por producto (una referencia puede venir en varias líneas).
    requested: Dict[str, int] = {}
    for item in return_data.items:
        if item.quantity <= 0:
            raise BusinessError(f"Cantidad inválida para el producto {item.barcode}: debe ser mayor a 0")
        requested[item.barcode] = requested.get(item.barcode, 0) + item.quantity

    async def _create(session):
        invoice = await invoices_repo.get(return_data.invoice_number, session=session)
        if not invoice:
            raise NotFoundError("Factura no encontrada")
        if invoice.get("status") == "returned":
            raise BusinessError("Esta factura ya fue devuelta por completo")

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
                raise BusinessError(f"El producto {barcode} no pertenece a la factura {return_data.invoice_number}")
            line = sold[barcode]
            available = line["quantity"] - returned_before.get(barcode, 0)
            if qty > available:
                raise BusinessError(f"Solo se pueden devolver {max(available, 0)} unidad(es) de {line['product_name']} "
                           f"(vendidas {line['quantity']}, ya devueltas {returned_before.get(barcode, 0)})")
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

        await invoices_repo.update(return_data.invoice_number, update_data, session=session)

        # Reingreso al inventario y movimientos.
        for item in return_items:
            await products_repo.add_stock(item["barcode"], item["quantity"], session=session)
            await products_repo.record_movement(barcode=item["barcode"], product_name=item["product_name"], movement_type="return",
                                                quantity=item["quantity"], reference=return_data.invoice_number,
                                                created_by=current_user.email, created_at=now, session=session)

        await audit.record("returns", "create", entity_id=return_data.invoice_number, entity_name=invoice.get("client_name"),
                           summary=f"Devolución sobre la factura {return_data.invoice_number} por {total_return:,.0f} "
                                   f"({sum(i['quantity'] for i in return_items)} unidad(es)); la factura queda "
                                   f"{'devuelta por completo' if fully_returned else 'con devolución parcial'}"
                                   + (f"; reembolso en efectivo {refund:,.0f}".replace(",", ".") if refund > 0 else ""),
                           before={k: invoice.get(k) for k in update_data}, after=update_data,
                           details={"items": return_items}, session=session)

        return return_dict

    return_dict = await run_in_transaction(_create)
    return {**return_dict, "created_at": as_datetime(return_dict["created_at"])}
