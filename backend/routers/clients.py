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

router = APIRouter(tags=["Clients"])
db_dep = Depends(get_db)
# ==================== DOCUMENT TYPES ====================

@router.post("/document-types", response_model=DocumentType)
async def create_document_type(doc_type: DocumentTypeCreate, current_user: User = Depends(get_current_user)):
    existing = await db.document_types.find_one({"code": doc_type.code})
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    dt_dict = doc_type.model_dump()
    dt_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.document_types.insert_one(dt_dict)
    return DocumentType(**dt_dict)

@router.get("/document-types", response_model=List[DocumentType])
async def get_document_types(current_user: User = Depends(get_current_user)):
    doc_types = await db.document_types.find({}, {"_id": 0}).to_list(1000)
    for dt in doc_types:
        if isinstance(dt.get('created_at'), str):
            dt['created_at'] = datetime.fromisoformat(dt['created_at'])
    return doc_types

# ==================== CLIENTS ====================

@router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user)):
    existing = await db.clients.find_one({
        "document_type": client.document_type,
        "document_number": client.document_number
    })
    if existing:
        raise HTTPException(status_code=400, detail="Client already exists")
    
    client_dict = client.model_dump()
    client_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.clients.insert_one(client_dict)
    return Client(**client_dict)

@router.get("/clients", response_model=List[Client])
async def get_clients(search: Optional[str] = None, current_user: User = Depends(get_current_user)):
    query = {}
    if search:
        query = {"$or": [
            {"document_number": {"$regex": search, "$options": "i"}},
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}}
        ]}
    
    clients = await db.clients.find(query, {"_id": 0}).to_list(1000)
    for client in clients:
        if isinstance(client.get('created_at'), str):
            client['created_at'] = datetime.fromisoformat(client['created_at'])
    return clients

@router.get("/clients/{document_number}", response_model=Client)
async def get_client(document_number: str, current_user: User = Depends(get_current_user)):
    client = await db.clients.find_one({"document_number": document_number}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if isinstance(client.get('created_at'), str):
        client['created_at'] = datetime.fromisoformat(client['created_at'])
    return Client(**client)

@router.put("/clients/{document_number}", response_model=Client)
async def update_client(document_number: str, client_update: ClientUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in client_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    result = await db.clients.update_one({"document_number": document_number}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    updated = await db.clients.find_one({"document_number": document_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Client(**updated)

@router.delete("/clients/{document_number}")
async def delete_client(document_number: str, current_user: User = Depends(get_current_user)):
    result = await db.clients.delete_one({"document_number": document_number})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted"}

# ==================== SUPPLIERS ====================

@router.post("/suppliers", response_model=Supplier)
async def create_supplier(supplier: SupplierCreate, current_user: User = Depends(get_current_user)):
    supp_dict = supplier.model_dump()
    supp_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.suppliers.insert_one(supp_dict)
    return Supplier(**supp_dict)

@router.get("/suppliers", response_model=List[Supplier])
async def get_suppliers(current_user: User = Depends(get_current_user)):
    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(1000)
    for supp in suppliers:
        if isinstance(supp.get('created_at'), str):
            supp['created_at'] = datetime.fromisoformat(supp['created_at'])
    return suppliers

@router.put("/suppliers/{supplier_name}", response_model=Supplier)
async def update_supplier(supplier_name: str, supplier_update: SupplierUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in supplier_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    result = await db.suppliers.update_one({"name": supplier_name}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    updated = await db.suppliers.find_one({"name": update_data.get("name", supplier_name)}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Supplier(**updated)

@router.delete("/suppliers/{supplier_name}")
async def delete_supplier(supplier_name: str, current_user: User = Depends(get_current_user)):
    result = await db.suppliers.delete_one({"name": supplier_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"message": "Supplier deleted"}

