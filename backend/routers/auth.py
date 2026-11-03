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

router = APIRouter(tags=["Auth"])
db_dep = Depends(get_db)
# ==================== AUTH ROUTES ====================

@router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    # Check in users_extended
    existing = await db.users_extended.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_data.password)
    
    # Create user in users_extended
    user_dict = {
        "email": user_data.email,
        "first_name": user_data.full_name.split()[0] if user_data.full_name else "Usuario",
        "last_name": " ".join(user_data.full_name.split()[1:]) if user_data.full_name and len(user_data.full_name.split()) > 1 else "",
        "phone": None,
        "is_active": True,
        "roles": ["Vendedor"],  # Default role
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users_extended.insert_one(user_dict)
    
    # Return User format for compatibility
    return User(
        email=user_dict["email"],
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

@router.post("/auth/login")
async def login(credentials: UserLogin):
    # Try users_extended first
    user = await db.users_extended.find_one({"email": credentials.email})
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User account is inactive")
    
    access_token = create_access_token(data={"sub": user["email"]})
    
    # Get user permissions from rbac module
    from routers.rbac import get_user_permissions
    user_permissions = await get_user_permissions(db, user["email"])
    
    # Convert permissions to simple dict
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user["email"],
            "full_name": f"{user['first_name']} {user['last_name']}",
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "roles": user.get("roles", []),
            "is_active": user.get("is_active", True),
            "permissions": permissions_dict
        }
    }

@router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    # Get full user data from users_extended
    user = await db.users_extended.find_one({"email": current_user.email}, {"_id": 0, "hashed_password": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get permissions
    from server_rbac import get_user_permissions
    user_permissions = await get_user_permissions(db, user["email"])
    
    permissions_dict = {}
    for module_slug, perms in user_permissions.items():
        permissions_dict[module_slug] = {
            "read": perms.read,
            "create": perms.create,
            "update": perms.update,
            "delete": perms.delete
        }
    
    return {
        "email": user["email"],
        "full_name": f"{user['first_name']} {user['last_name']}",
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "roles": user.get("roles", []),
        "is_active": user.get("is_active", True),
        "permissions": permissions_dict
    }

