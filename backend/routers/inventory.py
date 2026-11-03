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

router = APIRouter(tags=["Inventory"])
db_dep = Depends(get_db)
# ==================== PURCHASES ====================

@router.post("/purchases", response_model=Purchase)
async def create_purchase(purchase_data: PurchaseCreate, current_user: User = Depends(get_current_user)):
    total = sum(item.total for item in purchase_data.items)
    
    # Generate purchase_number
    last = await db.purchases.find_one({}, sort=[("purchase_number", -1)])
    if last and last.get("purchase_number"):
        num = int(last["purchase_number"].replace("PUR-", "")) + 1
    else:
        num = 1
    purchase_number = f"PUR-{num:06d}"
    
    purchase_dict = {
        "purchase_number": purchase_number,
        "supplier_name": purchase_data.supplier_name,
        "items": [item.model_dump() for item in purchase_data.items],
        "total": total,
        "status": "borrador",
        "created_by": current_user.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.purchases.insert_one(purchase_dict)
    
    return Purchase(**{**purchase_dict, "created_at": datetime.fromisoformat(purchase_dict["created_at"])})

@router.get("/purchases/{purchase_number}", response_model=Purchase)
async def get_purchase(purchase_number: str, current_user: User = Depends(get_current_user)):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if isinstance(purchase.get('created_at'), str):
        purchase['created_at'] = datetime.fromisoformat(purchase['created_at'])
    return Purchase(**purchase)

@router.put("/purchases/{purchase_number}", response_model=Purchase)
async def update_purchase(purchase_number: str, update_data: PurchaseUpdate, current_user: User = Depends(get_current_user)):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number})
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if purchase.get("status") != "borrador":
        raise HTTPException(status_code=400, detail="No se puede editar una compra confirmada")
    
    update_fields = {}
    if update_data.supplier_name is not None:
        update_fields["supplier_name"] = update_data.supplier_name
    if update_data.items is not None:
        items_dump = [item.model_dump() for item in update_data.items]
        update_fields["items"] = items_dump
        update_fields["total"] = sum(item.total for item in update_data.items)
    
    if update_fields:
        await db.purchases.update_one({"purchase_number": purchase_number}, {"$set": update_fields})
    
    updated = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Purchase(**updated)

@router.post("/purchases/{purchase_number}/confirm", response_model=Purchase)
async def confirm_purchase(purchase_number: str, current_user: User = Depends(get_current_user)):
    purchase = await db.purchases.find_one({"purchase_number": purchase_number})
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if purchase.get("status") != "borrador":
        raise HTTPException(status_code=400, detail="Esta compra ya está confirmada")
    
    await db.purchases.update_one({"purchase_number": purchase_number}, {"$set": {"status": "confirmado"}})
    
    for item in purchase["items"]:
        await db.products.update_one(
            {"barcode": item["barcode"]},
            {"$inc": {"stock": item["quantity"]}}
        )
        movement_dict = {
            "barcode": item["barcode"],
            "product_name": item["product_name"],
            "movement_type": "purchase",
            "quantity": item["quantity"],
            "reference": purchase_number,
            "created_by": current_user.email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.inventory_movements.insert_one(movement_dict)
    
    updated = await db.purchases.find_one({"purchase_number": purchase_number}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Purchase(**updated)

@router.get("/purchases", response_model=List[Purchase])
async def get_purchases(current_user: User = Depends(get_current_user)):
    purchases = await db.purchases.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for purch in purchases:
        if isinstance(purch.get('created_at'), str):
            purch['created_at'] = datetime.fromisoformat(purch['created_at'])
    return purchases

# ==================== INVENTORY ====================

@router.get("/inventory", response_model=List[Product])
async def get_inventory(current_user: User = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    for prod in products:
        if isinstance(prod.get('created_at'), str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
    return products

@router.get("/inventory/movements", response_model=List[InventoryMovement])
async def get_inventory_movements(
    barcode: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if barcode:
        query["barcode"] = barcode
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for mov in movements:
        if isinstance(mov.get('created_at'), str):
            mov['created_at'] = datetime.fromisoformat(mov['created_at'])
    return movements

