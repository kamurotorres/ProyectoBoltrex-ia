import sys
from pathlib import Path

def main():
    with open("backend/server.py", "r", encoding="utf-8") as f:
        content = f.read()

    def extract_block(start_marker, end_marker=None):
        start_idx = content.find(start_marker)
        if start_idx == -1: return ""
        if end_marker:
            end_idx = content.find(end_marker, start_idx + len(start_marker))
            if end_idx == -1:
                return content[start_idx:]
            return content[start_idx:end_idx]
        return content[start_idx:]

    blocks = {
        "AUTH ROUTES": extract_block("# ==================== AUTH ROUTES ====================", "# ==================== CATEGORIES ===================="),
        "CATEGORIES": extract_block("# ==================== CATEGORIES ====================", "# ==================== PRICE LISTS ===================="),
        "PRICE LISTS": extract_block("# ==================== PRICE LISTS ====================", "# ==================== PRODUCTS ===================="),
        "PRODUCTS": extract_block("# ==================== PRODUCTS ====================", "# ==================== DOCUMENT TYPES ===================="),
        "DOCUMENT TYPES": extract_block("# ==================== DOCUMENT TYPES ====================", "# ==================== CLIENTS ===================="),
        "CLIENTS": extract_block("# ==================== CLIENTS ====================", "# ==================== SUPPLIERS ===================="),
        "SUPPLIERS": extract_block("# ==================== SUPPLIERS ====================", "# ==================== TAX RATES ===================="),
        "TAX RATES": extract_block("# ==================== TAX RATES ====================", "# ==================== PAYMENT METHODS ===================="),
        "PAYMENT METHODS": extract_block("# ==================== PAYMENT METHODS ====================", "# ==================== INVOICES (POS) ===================="),
        "INVOICES": extract_block("# ==================== INVOICES (POS) ====================", "# ==================== RETURNS ===================="),
        "RETURNS": extract_block("# ==================== RETURNS ====================", "# ==================== FIOS (CREDITS/PAYMENTS) ===================="),
        "FIOS": extract_block("# ==================== FIOS (CREDITS/PAYMENTS) ====================", "# ==================== PURCHASES ===================="),
        "PURCHASES": extract_block("# ==================== PURCHASES ====================", "# ==================== INVENTORY ===================="),
        "INVENTORY": extract_block("# ==================== INVENTORY ====================", "# ==================== REPORTS ===================="),
        "REPORTS": extract_block("# ==================== REPORTS ====================", "# ==================== DASHBOARD STATS ===================="),
        "DASHBOARD": extract_block("# ==================== DASHBOARD STATS ====================", "# ==================== IMPORT ENDPOINTS ===================="),
        "IMPORT": extract_block("# ==================== IMPORT ENDPOINTS ====================", "# ==================== TICKET CONFIGURATION ===================="),
        "TICKET": extract_block("# ==================== TICKET CONFIGURATION ====================", "# ==================== INVOICES ENHANCED (WITH PDF TICKETS) ===================="),
        "INVOICES_ENHANCED": extract_block("# ==================== INVOICES ENHANCED (WITH PDF TICKETS) ====================", "# ==================== FACTORY RESET ===================="),
        "RESET": extract_block("# ==================== FACTORY RESET ====================")
    }

    base_imports = """from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request, Response, BackgroundTasks
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
"""

    routers = {
        "auth": base_imports + '\nrouter = APIRouter(tags=["Auth"])\ndb_dep = Depends(get_db)\n' + blocks["AUTH ROUTES"],
        "products": base_imports + '\nrouter = APIRouter(tags=["Products"])\ndb_dep = Depends(get_db)\n' + blocks["CATEGORIES"] + blocks["PRICE LISTS"] + blocks["PRODUCTS"],
        "clients": base_imports + '\nrouter = APIRouter(tags=["Clients"])\ndb_dep = Depends(get_db)\n' + blocks["DOCUMENT TYPES"] + blocks["CLIENTS"] + blocks["SUPPLIERS"],
        "invoices": base_imports + '\nrouter = APIRouter(tags=["Billing"])\ndb_dep = Depends(get_db)\n' + blocks["TAX RATES"] + blocks["PAYMENT METHODS"] + blocks["INVOICES"] + blocks["RETURNS"] + blocks["FIOS"] + blocks["INVOICES_ENHANCED"],
        "inventory": base_imports + '\nrouter = APIRouter(tags=["Inventory"])\ndb_dep = Depends(get_db)\n' + blocks["PURCHASES"] + blocks["INVENTORY"],
        "reports": base_imports + '\nrouter = APIRouter(tags=["Reports"])\ndb_dep = Depends(get_db)\n' + blocks["REPORTS"] + blocks["DASHBOARD"],
        "system": base_imports + '\nrouter = APIRouter(tags=["System"])\ndb_dep = Depends(get_db)\n' + blocks["IMPORT"] + blocks["TICKET"] + blocks["RESET"]
    }

    for name, code in routers.items():
        code = code.replace("@api_router", "@router")
        code = code.replace("Depends(get_db)", "Depends(get_db)") # Leave it, wait no, they use `db.` directly.
        # But wait, original code used global `db`, not injected. Let's just import `db` from core.database.
        code = code.replace("db: AsyncIOMotorDatabase = Depends(get_db)", "current_user: User = Depends(get_current_user)") # just an ugly hack for a parameter signature replace, but easier:
        # Instead, just leave original code. It uses `db.collections...` which is the global db.
        with open(f"backend/routers/{name}.py", "w", encoding="utf-8") as f:
            f.write(code)

if __name__ == "__main__":
    main()
