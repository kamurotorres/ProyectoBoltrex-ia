"""Identificación de clientes por tipo + número de documento (backlog P1.15).

Un cliente es único por (document_type, document_number): una CC 123 y un NIT 123 son
clientes distintos. Toda búsqueda de un cliente concreto pasa por `resolve_client`:
- con tipo → coincidencia exacta;
- sin tipo y un solo cliente con ese número → ese (compatibilidad con llamadas antiguas);
- sin tipo y varios → error con mensaje: nunca se adivina.
"""
import logging


from core.database import db

# Búsqueda del cliente: repositories/clients.py (fase 3). Se reexporta por compatibilidad.
from repositories.clients import client_label, invoices_of_client_query, resolve_client  # noqa: F401,E402

logger = logging.getLogger("boltrex")


async def backfill_invoice_document_types() -> dict:
    """Al arrancar: completa `client_document_type` en facturas antiguas cuando hay un solo
    cliente posible con ese número. Las ambiguas se dejan sin tocar y se informan en el log.
    Nunca impide el arranque."""
    report = {"updated": 0, "ambiguous": [], "orphan": 0}
    try:
        numbers = await db.invoices.distinct(
            "client_document", {"$or": [{"client_document_type": {"$exists": False}}, {"client_document_type": None}]}
        )
        for number in numbers:
            types = await db.clients.distinct("document_type", {"document_number": number})
            if len(types) == 1:
                res = await db.invoices.update_many(
                    {"client_document": number,
                     "$or": [{"client_document_type": {"$exists": False}}, {"client_document_type": None}]},
                    {"$set": {"client_document_type": types[0]}},
                )
                report["updated"] += res.modified_count
            elif len(types) > 1:
                report["ambiguous"].append(number)
            else:
                report["orphan"] += 1
        if report["updated"]:
            logger.info("Facturas antiguas: se completó el tipo de documento del cliente en %d factura(s).", report["updated"])
        if report["ambiguous"]:
            logger.warning(
                "Facturas sin tipo de documento con número compartido por varios clientes (no se tocaron): %s",
                ", ".join(report["ambiguous"][:20]),
            )
    except Exception as exc:  # pragma: no cover - solo registro
        logger.error("No se pudo completar el tipo de documento en facturas antiguas: %s", exc)
    return report
