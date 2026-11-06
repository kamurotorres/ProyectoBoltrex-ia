"""Identificación de clientes por tipo + número de documento (backlog P1.15).

Un cliente es único por (document_type, document_number): una CC 123 y un NIT 123 son
clientes distintos. Toda búsqueda de un cliente concreto pasa por `resolve_client`:
- con tipo → coincidencia exacta;
- sin tipo y un solo cliente con ese número → ese (compatibilidad con llamadas antiguas);
- sin tipo y varios → error con mensaje: nunca se adivina.

(Mantenimiento fase 3: movido de core/clients.py a la capa de repositorios.)
"""
from typing import Optional

from core.database import db
from core.errors import BusinessError, NotFoundError


def client_label(document_type: Optional[str], document_number: str) -> str:
    return f"{document_type} {document_number}".strip() if document_type else str(document_number)


async def resolve_client(document_number: str, document_type: Optional[str] = None, session=None,
                         projection: Optional[dict] = None) -> dict:
    projection = projection if projection is not None else {"_id": 0}
    document_type = (document_type or "").strip() or None
    if document_type:
        client = await db.clients.find_one({"document_type": document_type, "document_number": document_number},
                                           projection, session=session)
        if not client:
            raise NotFoundError(f"No existe un cliente con el documento {client_label(document_type, document_number)}.")
        return client

    matches = await db.clients.find({"document_number": document_number}, projection, session=session).to_list(10)
    if not matches:
        raise NotFoundError(f"No existe un cliente con el documento {document_number}.")
    if len(matches) > 1:
        types = ", ".join(sorted({m.get("document_type", "?") for m in matches}))
        raise BusinessError(f"Hay {len(matches)} clientes con el documento {document_number} ({types}). "
                   f"Indica el tipo de documento.")
    return matches[0]


def invoices_of_client_query(client: dict) -> dict:
    """Facturas de un cliente: las que guardan su tipo y, de las antiguas sin tipo, las de su número."""
    return {
        "client_document": client["document_number"],
        "$or": [
            {"client_document_type": client.get("document_type")},
            {"client_document_type": {"$exists": False}},
            {"client_document_type": None},
        ],
    }
