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

router = APIRouter(tags=["Reports"])
db_dep = Depends(get_db)
# ==================== REPORTS ====================

@router.get("/reports/sales")
async def get_sales_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {"status": "completed"}
    if start_date or end_date:
        query["created_at"] = {}
        if start_date:
            query["created_at"]["$gte"] = start_date
        if end_date:
            query["created_at"]["$lte"] = end_date
    
    invoices = await db.invoices.find(query, {"_id": 0}).to_list(1000)
    
    total_sales = sum(inv["total"] for inv in invoices)
    total_tax = sum(inv["total_tax"] for inv in invoices)
    
    return {
        "invoices": invoices,
        "summary": {
            "total_invoices": len(invoices),
            "total_sales": total_sales,
            "total_tax": total_tax
        }
    }

@router.get("/reports/inventory")
async def get_inventory_report(current_user: User = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    
    total_value = sum(p["purchase_price"] * p["stock"] for p in products)
    low_stock = [p for p in products if p["stock"] < 10]
    
    return {
        "products": products,
        "summary": {
            "total_products": len(products),
            "total_value": total_value,
            "low_stock_count": len(low_stock)
        }
    }

# ==================== DASHBOARD STATS ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    # Count documents
    total_products = await db.products.count_documents({})
    total_clients = await db.clients.count_documents({})
    total_invoices = await db.invoices.count_documents({"status": "completed"})
    
    # Calculate total sales
    invoices = await db.invoices.find({"status": "completed"}, {"_id": 0, "total": 1}).to_list(10000)
    total_sales = sum(inv["total"] for inv in invoices)
    
    # Low stock products
    low_stock = await db.products.count_documents({"stock": {"$lt": 10}})
    
    return {
        "total_products": total_products,
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_sales": total_sales,
        "low_stock_products": low_stock
    }

