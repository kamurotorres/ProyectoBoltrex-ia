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

router = APIRouter(tags=["Products"])
db_dep = Depends(get_db)
# ==================== CATEGORIES ====================

@router.post("/categories", response_model=Category)
async def create_category(category: CategoryCreate, current_user: User = Depends(get_current_user)):
    existing = await db.categories.find_one({"name": category.name})
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    cat_dict = category.model_dump()
    cat_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.categories.insert_one(cat_dict)
    return Category(**cat_dict)

@router.get("/categories", response_model=List[Category])
async def get_categories(current_user: User = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    for cat in categories:
        if isinstance(cat.get('created_at'), str):
            cat['created_at'] = datetime.fromisoformat(cat['created_at'])
    return categories

@router.put("/categories/{name}", response_model=Category)
async def update_category(name: str, category: CategoryCreate, current_user: User = Depends(get_current_user)):
    result = await db.categories.update_one(
        {"name": name},
        {"$set": category.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    updated = await db.categories.find_one({"name": name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Category(**updated)

@router.delete("/categories/{name}")
async def delete_category(name: str, current_user: User = Depends(get_current_user)):
    result = await db.categories.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}

# ==================== PRICE LISTS ====================

@router.post("/price-lists", response_model=PriceList)
async def create_price_list(price_list: PriceListCreate, current_user: User = Depends(get_current_user)):
    pl_dict = price_list.model_dump()
    pl_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.price_lists.insert_one(pl_dict)
    return PriceList(**pl_dict)

@router.get("/price-lists", response_model=List[PriceList])
async def get_price_lists(current_user: User = Depends(get_current_user)):
    price_lists = await db.price_lists.find({}, {"_id": 0}).to_list(1000)
    for pl in price_lists:
        if isinstance(pl.get('created_at'), str):
            pl['created_at'] = datetime.fromisoformat(pl['created_at'])
    return price_lists

@router.put("/price-lists/{name}", response_model=PriceList)
async def update_price_list(name: str, pl_update: PriceListUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in pl_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    result = await db.price_lists.update_one({"name": name}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Price list not found")
    new_name = update_data.get("name", name)
    updated = await db.price_lists.find_one({"name": new_name}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return PriceList(**updated)

@router.delete("/price-lists/{name}")
async def delete_price_list(name: str, current_user: User = Depends(get_current_user)):
    result = await db.price_lists.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Price list not found")
    return {"message": "Price list deleted"}

# ==================== PRODUCTS ====================

@router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, current_user: User = Depends(get_current_user)):
    existing = await db.products.find_one({"barcode": product.barcode})
    if existing:
        raise HTTPException(status_code=400, detail="Barcode already exists")
    
    prod_dict = product.model_dump()
    prod_dict["stock"] = 0
    prod_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.products.insert_one(prod_dict)
    return Product(**prod_dict)

@router.get("/products", response_model=List[Product])
async def get_products(search: Optional[str] = None, current_user: User = Depends(get_current_user)):
    query = {}
    if search:
        query = {"$or": [
            {"barcode": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]}
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    for prod in products:
        if isinstance(prod.get('created_at'), str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
    return products

@router.get("/products/{barcode}", response_model=Product)
async def get_product(barcode: str, current_user: User = Depends(get_current_user)):
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if isinstance(product.get('created_at'), str):
        product['created_at'] = datetime.fromisoformat(product['created_at'])
    return Product(**product)

@router.put("/products/{barcode}", response_model=Product)
async def update_product(barcode: str, product_update: ProductUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in product_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    result = await db.products.update_one({"barcode": barcode}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    updated = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return Product(**updated)

@router.delete("/products/{barcode}")
async def delete_product(barcode: str, current_user: User = Depends(get_current_user)):
    result = await db.products.delete_one({"barcode": barcode})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}

