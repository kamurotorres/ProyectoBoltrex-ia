"""Paginación en el servidor para los listados que crecen (backlog P1.18).

Todos responden con el mismo formato:
    {"items": [...], "total": N, "page": p, "page_size": s, "pages": P}

- `page` empieza en 1; `page_size` entre 1 y MAX_PAGE_SIZE (por defecto DEFAULT_PAGE_SIZE).
- Una página fuera de rango devuelve `items` vacío (no error), con `total` y `pages` reales.
- La búsqueda (`search`) se hace en la base de datos: encuentra cualquier registro, no solo
  los de la página. Se escapan los caracteres especiales (sin regex inyectadas).
- El orden siempre termina en `_id` para que las páginas no se repitan ni se salten registros
  cuando varios documentos tienen el mismo valor de orden.
"""
import math
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fastapi import Query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def page_params(page: int = Query(1, ge=1, description="Página (desde 1)"),
                page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Registros por página")):
    return {"page": page, "page_size": page_size}


def search_filter(search: Optional[str], fields: Iterable[str]) -> Optional[dict]:
    text = (search or "").strip()
    if not text:
        return None
    rx = {"$regex": re.escape(text), "$options": "i"}
    return {"$or": [{f: rx} for f in fields]}


def combine(*filters: Optional[dict]) -> dict:
    parts = [f for f in filters if f]
    if not parts:
        return {}
    return parts[0] if len(parts) == 1 else {"$and": parts}


def _with_tiebreak(sort: Sequence[Tuple[str, int]]) -> List[Tuple[str, int]]:
    sort = list(sort or [])
    if not any(k == "_id" for k, _ in sort):
        sort.append(("_id", sort[-1][1] if sort else 1))
    return sort


def envelope(items: list, total: int, page: int, page_size: int) -> Dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)) if page_size else 1}


async def paginate(collection, query: dict, sort: Sequence[Tuple[str, int]], page: int, page_size: int,
                   projection: Optional[dict] = None) -> Dict:
    projection = projection if projection is not None else {"_id": 0}
    total = await collection.count_documents(query)
    cursor = (collection.find(query, projection).sort(_with_tiebreak(sort))
              .skip((page - 1) * page_size).limit(page_size))
    items = await cursor.to_list(page_size)
    return envelope(items, total, page, page_size)


async def paginate_pipeline(collection, pipeline: list, sort: Sequence[Tuple[str, int]], page: int, page_size: int) -> Dict:
    """Paginación de una agregación (p. ej. cuentas de Fios agrupadas por cliente)."""
    sort_stage = {"$sort": dict(_with_tiebreak(sort))}
    facet = {"$facet": {
        "items": [sort_stage, {"$skip": (page - 1) * page_size}, {"$limit": page_size}],
        "total": [{"$count": "n"}],
    }}
    rows = await collection.aggregate(list(pipeline) + [facet]).to_list(1)
    data = rows[0] if rows else {"items": [], "total": []}
    total = data["total"][0]["n"] if data.get("total") else 0
    return envelope(data.get("items", []), total, page, page_size)
