"""Ticket PDF de una factura (con sus devoluciones) (mantenimiento fase 3)."""
from core.errors import NotFoundError
from core.database import db
from repositories import invoices as invoices_repo
from models.auth import User
from ticket_generator import TicketPDFGenerator




async def invoice_ticket_pdf(invoice_number: str, current_user: User):
    """Generar y descargar ticket PDF de una factura"""
    invoice = await invoices_repo.get(invoice_number)
    if not invoice:
        raise NotFoundError("Factura no encontrada")

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
    return pdf_buffer
